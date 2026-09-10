import argparse
import json
import logging
import os
from cumulative.disconnect import fetch_disconnect
from cumulative.duckduckgo import fetch_duckduckgo
from cumulative.easyprivacy import fetch_easyprivacy
from cumulative.webprivacy import fetch_webprivacy

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Stats")

RESULTS_DIR = "results"

START_DATE = "2025-10-20"
END_DATE = "2026-08-13"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)

def parse_args():
    parser = argparse.ArgumentParser(description="Report cumulative addition/removal stats per list.")
    parser.add_argument(
        "--disconnect-path",
        default=None,
        # default="cumulative/disconnect_domain_changes.json",
        help="Path to the Disconnect domain changes JSON file (default: %(default)s)"
    )
    parser.add_argument(
        "--duckduckgo-path",
        # default="cumulative/duckduckgo_domain_changes.json",
        help="Path to the DuckDuckGo domain changes JSON file (default: %(default)s)"
    )
    parser.add_argument(
        "--easyprivacy-path",
        # default="cumulative/easyprivacy_changes.json",
        help="Path to the EasyPrivacy changes JSON file (default: %(default)s)"
    )
    parser.add_argument(
        "--webprivacy-path",
        # default="cumulative/webprivacy_changes.json",
        help="Path to the WebPrivacy changes JSON file (default: %(default)s)"
    )
    return parser.parse_args()

def read_changes_file(file_path: str):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data

def main():
    args = parse_args()
    logger.info("Starting cumulative analysis...")

    # Check for GitHub token if not all four lists are provided
    if not all([args.disconnect_path, args.duckduckgo_path, args.easyprivacy_path, args.webprivacy_path]) and not GITHUB_TOKEN:
        logger.warning("No GitHub token provided. List crawling might fail due to rate limiting. Consider setting the GITHUB_TOKEN environment variable.")

    # Ensure output directory exists
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Disconnect data
    if args.disconnect_path:
        logger.info(f"Loading Disconnect data from {args.disconnect_path}...")
        disconnect_data = read_changes_file(args.disconnect_path)
    else:
        logger.info("Fetching Disconnect data...")
        disconnect_path = args.disconnect_path if args.disconnect_path else os.path.join(RESULTS_DIR, "disconnect_domain_changes.json")
        disconnect_data = fetch_disconnect(START_DATE, END_DATE, args.disconnect_path if args.disconnect_path else disconnect_path)
        

    # DuckDuckGo data
    if args.duckduckgo_path:
        logger.info(f"Loading DuckDuckGo data from {args.duckduckgo_path}...")
        duckduckgo_data = read_changes_file(args.duckduckgo_path)
    else:
        logger.info("Fetching DuckDuckGo data...")
        duckduckgo_path = args.duckduckgo_path if args.duckduckgo_path else os.path.join(RESULTS_DIR, "duckduckgo_domain_changes.json")
        custom_start_date = "2025-10-7" # fetch one commit earlier as baseline to fetch the first change within the range
        duckduckgo_data = fetch_duckduckgo(custom_start_date, END_DATE, args.duckduckgo_path if args.duckduckgo_path else duckduckgo_path)

    # EasyPrivacy data
    if args.easyprivacy_path:
        logger.info(f"Loading EasyPrivacy data from {args.easyprivacy_path}...")
        easyprivacy_data = read_changes_file(args.easyprivacy_path)
    else:
        logger.info("Fetching EasyPrivacy data (This may take several minutes)...")
        easyprivacy_path = args.easyprivacy_path if args.easyprivacy_path else os.path.join(RESULTS_DIR, "easyprivacy_changes.json")
        easyprivacy_data = fetch_easyprivacy(START_DATE, END_DATE, args.easyprivacy_path if args.easyprivacy_path else easyprivacy_path)

    # WebPrivacy data
    if args.webprivacy_path:
        logger.info(f"Loading WebPrivacy data from {args.webprivacy_path}...")
        webprivacy_data = read_changes_file(args.webprivacy_path)
    else:
        logger.info("Fetching WebPrivacy data...")
        webprivacy_path = args.webprivacy_path if args.webprivacy_path else os.path.join(RESULTS_DIR, "webprivacy_changes.json")
        webprivacy_data = fetch_webprivacy(START_DATE, END_DATE, args.webprivacy_path if args.webprivacy_path else webprivacy_path)

    # for each list, output the number of additions and removals
    added, removed = 0, 0
    for item in disconnect_data:
        added += len(item.get("domains_added", []))
        removed += len(item.get("domains_removed", []))
    logger.info(f"Disconnect: {added} domains added, {removed} domains removed (total changes: {added + removed})")

    added, removed = 0, 0
    for item in duckduckgo_data:
        added += len(item.get("domains_added", []))
        removed += len(item.get("domains_removed", []))
    logger.info(f"DuckDuckGo: {added} domains added, {removed} domains removed (total changes: {added + removed})")

    added, removed = 0, 0
    for item in easyprivacy_data:
        for inner_item in item.get("file_changes", []):
            added += len(inner_item.get("additions", []))
            removed += len(inner_item.get("removals", []))
    logger.info(f"EasyPrivacy: {added} domains added, {removed} domains removed (total changes: {added + removed})")

    added, removed = 0, 0
    for item in webprivacy_data:
        if item["list_name"] == "RESOURCE_MONITOR_URLS": # count external list changes as 1 change each
            added += 1
        else:
            added += len(item.get("added", []))
            removed += len(item.get("removed", []))
    logger.info(f"WebPrivacy: {added} entries added, {removed} entries removed (total changes: {added + removed})")

    logger.info("Cumulative analysis completed.")


if __name__ == "__main__":
    main()