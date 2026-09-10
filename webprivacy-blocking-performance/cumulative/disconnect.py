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
logger = logging.getLogger("DisconnectHistory")

OWNER = "disconnectme"
REPO = "disconnect-tracking-protection"
TARGET_FILE = "services.json"
    
START_DATE = "2025-10-20"
END_DATE = "2026-08-13"
OUTPUT_FILE = "cumulative/disconnect_domain_changes.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)


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

def get_file_commits(owner, repo, target_file, token=None, since=None, until=None):
    """Fetches the timeline of commits that touched the target file."""
    commits_data = []
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    params = {
        "path": target_file,
        "per_page": 100
    }
    
    if since:
        params["since"] = format_github_date(since, is_end_of_day=False)
    if until:
        params["until"] = format_github_date(until, is_end_of_day=True)
        
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    logger.debug(f"Starting timeline extraction for {owner}/{repo}/{target_file}")
    
    while url:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 403 and "rate limit" in response.text.lower():
            logger.error("GitHub API rate limit exceeded.")
            break
        elif response.status_code != 200:
            logger.error(f"Error fetching data: {response.status_code} - {response.text}")
            break
            
        page_commits = response.json()
        if not page_commits:
            break
            
        commits_data.extend(page_commits)
        
        if 'next' in response.links:
            url = response.links['next']['url']
            params = None
            time.sleep(0.5) 
        else:
            url = None
            
    return commits_data

def extract_disconnect_domains(json_data):
    """Flattens the deeply nested Disconnect JSON into a single set of tracking domains."""
    domains = set()
    
    # Disconnect stores everything under a top-level 'categories' key
    categories = json_data.get('categories', {})
    
    for category_name, entities in categories.items():
        for entity_dict in entities:
            for entity_name, entity_data in entity_dict.items():
                for main_url, domain_list in entity_data.items():
                    if isinstance(domain_list, list):
                        for domain in domain_list:
                            domains.add(domain)
    return domains

def get_raw_json_at_commit(owner, repo, sha, target_file):
    """Fetches the entire JSON file as it existed at a specific commit."""
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{target_file}"
    response = requests.get(raw_url)
    
    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON for commit {sha}. File may be corrupted.")
            return None
    else:
        logger.error(f"Failed to fetch raw file for {sha}: HTTP {response.status_code}")
        return None

def fetch_disconnect(start_date: str, end_date: str, output_file: str = OUTPUT_FILE) -> None:

    all_commits = get_file_commits(
        owner=OWNER, 
        repo=REPO, 
        target_file=TARGET_FILE, 
        token=GITHUB_TOKEN,
        since=start_date,
        until=end_date
    )
    
    if not all_commits:
        logger.error("No commits found. Exiting.")
        return

    all_commits.reverse()
    
    logger.debug(f"Analyzing {len(all_commits)} commits chronologically.")
    
    detailed_commit_history = []
    previous_domains_set = set()

    for index, commit in enumerate(all_commits):
        sha = commit['sha']
        date = commit['commit']['author']['date']
        message = commit['commit']['message'].split('\n')[0]
        
        logger.debug(f"Processing {index + 1}/{len(all_commits)}: {sha[:7]}...")
        
        # Fetch the full file state at this point in time
        raw_json = get_raw_json_at_commit(OWNER, REPO, sha, TARGET_FILE)
        
        if raw_json is None:
            continue
            
        # Extract a flat list of all active tracking domains
        current_domains_set = extract_disconnect_domains(raw_json)
        
        # If this isn't the first commit we are checking, compare it to the previous state
        additions = []
        removals = []
        
        if index > 0:
            additions = list(current_domains_set - previous_domains_set)
            removals = list(previous_domains_set - current_domains_set)
            
        # Only log the commit if actual domains changed (ignoring formatting/category moves)
        if index == 0 or additions or removals:
            detailed_commit_history.append({
                "sha": sha,
                "date": date,
                "message": message,
                "total_domains_active": len(current_domains_set),
                "domains_added": additions,
                "domains_removed": removals
            })
            
        # Update the state for the next iteration
        previous_domains_set = current_domains_set
        
        time.sleep(0.5)
    
    with open(output_file, 'w') as f:
        json.dump(detailed_commit_history, f, indent=4)
    logger.debug(f"Clean domain delta saved to {output_file}")

    total_additions = sum(len(commit['domains_added']) for commit in detailed_commit_history)
    total_removals = sum(len(commit['domains_removed']) for commit in detailed_commit_history)
    logger.debug(f"Total domains added: {total_additions}, Total domains removed: {total_removals}")

    return detailed_commit_history

if __name__ == "__main__":
    fetch_disconnect(START_DATE, END_DATE, OUTPUT_FILE)