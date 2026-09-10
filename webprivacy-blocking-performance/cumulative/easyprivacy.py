import requests
import time
import logging
import json
import os
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("EasyPrivacyHistory")

OWNER = "easylist"
REPO = "easylist"
FOLDER = "easyprivacy"
    
START_DATE = "2025-10-20"
END_DATE = "2026-08-13"

OUTPUT_FILE = "cumulative/easyprivacy_changes.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)

# If remaining requests drop to or below this, we start pausing before every call.
RATE_LIMIT_FLOOR = 5


def format_github_date(date_str, is_end_of_day=False):
    """Formats a YYYY-MM-DD string to GitHub's required ISO 8601 format."""
    try:
        if "T" in date_str and "Z" in date_str:
            return date_str 
            
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if is_end_of_day:
            return dt.strftime("%Y-%m-%dT23:59:59Z")
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    except ValueError:
        logger.error(f"Date '{date_str}' must be in YYYY-MM-DD format.")
        return None

def parse_patch(patch_text):
    additions = []
    removals = []
    
    if not patch_text:
        return additions, removals
        
    for line in patch_text.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            additions.append(line[1:].strip())
        elif line.startswith('-') and not line.startswith('---'):
            removals.append(line[1:].strip())
            
    return additions, removals

def throttle_from_headers(response_headers):
    
    remaining = response_headers.get("X-RateLimit-Remaining")
    reset = response_headers.get("X-RateLimit-Reset")

    if remaining is None or reset is None:
        # Headers missing (e.g. mocked responses in tests); fall back to a small pause.
        time.sleep(0.2)
        return

    remaining = int(remaining)
    reset = int(reset)

    if remaining <= RATE_LIMIT_FLOOR:
        wait_seconds = max(reset - time.time(), 0) + 1
        logger.warning(
            f"Only {remaining} requests remaining. Sleeping {wait_seconds:.1f}s until rate limit reset."
        )
        time.sleep(wait_seconds)

def get_commit_file_changes(owner, repo, sha, target_folder, headers):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    response = requests.get(url, headers=headers)

    throttle_from_headers(response.headers)

    if response.status_code == 403 and "rate limit" in response.text.lower():
        logger.error("Rate limit hit while fetching commit diffs.")
        return None
    elif response.status_code != 200:
        logger.error(f"Failed to fetch commit {sha}: {response.status_code}")
        return None
        
    commit_data = response.json()
    folder_changes = []
    
    for file in commit_data.get('files', []):
        filename = file.get('filename', '')
        
        if filename.startswith(f"{target_folder}/"):
            patch = file.get('patch', '')
            added, removed = parse_patch(patch)
            
            folder_changes.append({
                "file": filename,
                "additions": added,
                "removals": removed
            })
            
    return folder_changes

def get_folder_commits(owner, repo, folder_path, token=None, since=None, until=None):
    commits_data = []
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    params = {
        "path": folder_path,
        "per_page": 100
    }
    
    if since:
        params["since"] = format_github_date(since, is_end_of_day=False)
    if until:
        params["until"] = format_github_date(until, is_end_of_day=True)
        
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    logger.debug(f"Starting extraction for {owner}/{repo}/{folder_path}")
    
    while url:
        response = requests.get(url, headers=headers, params=params)

        throttle_from_headers(response.headers)

        if response.status_code == 403 and "rate limit" in response.text.lower():
            logger.error("GitHub API rate limit exceeded. You need to use a Personal Access Token.")
            break
        elif response.status_code != 200:
            logger.error(f"Error fetching data: {response.status_code} - {response.text}")
            break
            
        page_commits = response.json()
        
        if not page_commits:
            break
            
        commits_data.extend(page_commits)
        logger.debug(f"Retrieved {len(page_commits)} commits. Total so far: {len(commits_data)}")
        
        if 'next' in response.links:
            url = response.links['next']['url']
            params = None
        else:
            url = None
            
    return commits_data

def fetch_easyprivacy(start_date: str, end_date: str, output_file: str = OUTPUT_FILE) -> None:
    
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        logger.debug("Using provided GitHub token for authentication.")

    all_commits = get_folder_commits(
        owner=OWNER, 
        repo=REPO, 
        folder_path=FOLDER, 
        token=GITHUB_TOKEN,
        since=start_date,
        until=end_date
    )
    
    if not all_commits:
        logger.error("No commits found or rate limit hit on initial fetch. Exiting.")
        return

    logger.debug(f"Finished extracting list. Total commits found: {len(all_commits)}")
    
    detailed_commit_history = []

    # Loop through each commit to fetch the line-by-line diffs
    for index, commit in enumerate(all_commits):
        sha = commit['sha']
        date = commit['commit']['author']['date']
        message = commit['commit']['message'].split('\n')[0]
        
        logger.debug(f"Processing diffs for {index + 1}/{len(all_commits)}: {sha[:7]}...")
        
        changes = get_commit_file_changes(OWNER, REPO, sha, FOLDER, headers)
        
        # If changes is None, we likely hit a rate limit error
        if changes is None:
            logger.warning("Halting diff extraction due to API errors.")
            break
            
        detailed_commit_history.append({
            "sha": sha,
            "date": date,
            "message": message,
            "file_changes": changes
        })
    
    with open(output_file, 'w') as f:
        json.dump(detailed_commit_history, f, indent=4)
    logger.debug(f"Detailed commits data saved to {output_file}")

    # total_additions and total_removals can be calculated from the detailed_commit_history if needed
    total_additions = sum(len(change["additions"]) for commit in detailed_commit_history for change in commit["file_changes"])
    total_removals = sum(len(change["removals"]) for commit in detailed_commit_history for change in commit["file_changes"])
    logger.debug(f"Total additions: {total_additions}")
    logger.debug(f"Total removals: {total_removals}")

    return detailed_commit_history

if __name__ == "__main__":
    fetch_easyprivacy(START_DATE, END_DATE, OUTPUT_FILE)