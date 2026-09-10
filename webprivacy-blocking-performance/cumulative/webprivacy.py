import os
import re
import logging
import json
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# add out file
logger = logging.getLogger("WebPrivacyHistory")

INPUT_DIR = "/data/webprivacy-lists"
AVAILABLE_LISTS = ["URL_FILTER", "STORAGE_ACCESS_USER_AGENT_STRING_QUIRKS", "STORAGE_ACCESS_PROMPT_QUIRKS", "QUERY_PARAM", "ALLOWED_QUERY_PARAM", "RESTRICTED_OPENER_DOMAINS", "FINGERPRINTING_SCRIPTS", "TRACKING_SUBNETS", "TRACKING_DOMAINS", "RESOURCE_MONITOR_URLS"]

START_DATE = "2025-10-20"
END_DATE = "2026-08-13"

OUTPUT_FILE = "cumulative/webprivacy_changes.json"

def get_sorted_folders(directory):
    
    folders_with_dates = []
    
    if not os.path.exists(directory):
        logger.error(f"Directory {directory} does not exist.")
        return []

    for entry in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, entry)):
            try:
                # Parse date and time assuming name format is "output_DDMMYYYY_HHMM"
                parts = entry.split("_")
                date = parts[1]
                time = parts[2] 
                date_time_obj = datetime.strptime(f"{date} {time}", "%d%m%Y %H%M")
                folders_with_dates.append((date_time_obj, entry))
            except (IndexError, ValueError) as e:
                logger.warning(f"Could not parse date from folder name '{entry}'. Error: {e}")
                
    folders_with_dates.sort(key=lambda x: x[0])
    return folders_with_dates

def read_json_file(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def extract_filter_list_version(raw_items):
    """Pull the version number out of a header line like '#  1:# Filter List: 9.56.0'.
    Returns None if no such line is found so callers can detect a missing/changed header format."""
    for item in raw_items:
        if "Filter List:" in item:
            match = re.search(r"Filter List:\s*([\d.]+)", item)
            if match:
                return match.group(1)
            logger.warning(f"Found 'Filter List:' line but could not parse a version from it: {item!r}")
            return None
    logger.warning("No 'Filter List:' header line found in RESOURCE_MONITOR_URLS additions.")
    return None

def fetch_webprivacy(start_date: str, end_date: str, output_file: str = OUTPUT_FILE) -> None:
    logger.debug("Starting analysis of WebPrivacy framework data...")
    
    sorted_folders = get_sorted_folders(INPUT_DIR)
    logger.debug(f"Found {len(sorted_folders)} valid output folders covering {int(len(sorted_folders) / 2)} days.")
    
    # log starting and end date of the timeline
    if sorted_folders:
        start_date = sorted_folders[0][0]
        end_date = sorted_folders[-1][0]
        logger.debug(f"Timeline covers from {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}.")
    else:
        logger.warning("No valid folders found. Exiting analysis.")
        return

    output_changes = []

    previous_states = {list_name: set() for list_name in AVAILABLE_LISTS}
    for dt_obj, folder in sorted_folders:
        logger.debug(f"Processing snapshot from: {dt_obj} (Folder: {folder})")

        # Iterate through each list
        for list_name in AVAILABLE_LISTS:

            # Read file
            file_path = os.path.join(INPUT_DIR, folder, f"{list_name}.json")
            if os.path.exists(file_path):

                data = read_json_file(file_path)
                raw_items = data.get("additions", [])
                if list_name == "RESOURCE_MONITOR_URLS":
                    current_items = set([item for item in raw_items if not item.startswith("#")])
                else:
                    current_items = set(raw_items)

                if list_name == "RESOURCE_MONITOR_URLS":
                    # External list: don't itemize contents, just record the version it was updated to.
                    if previous_states[list_name]:
                        if current_items != previous_states[list_name]:
                            version = extract_filter_list_version(raw_items)
                            logger.debug(f"External list {list_name} changed on {dt_obj.strftime('%Y-%m-%d %H:%M')} (updated to version {version})")
                            output_changes.append({
                                "date": dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "list_name": list_name,
                                "version": version
                            })
                        else:
                            logger.debug(f"No changes in {list_name}.")
                    else:
                        logger.debug(f"Initial state loaded for {list_name} ({len(current_items)} items).")
                else:
                    # If we have previous state, compare and log changes
                    if previous_states[list_name]:
                        newly_added = current_items - previous_states[list_name]
                        newly_removed = previous_states[list_name] - current_items

                        if newly_added or newly_removed:
                            logger.debug(f"Changes detected in {list_name} on {dt_obj.strftime('%Y-%m-%d %H:%M')}:")
                            if newly_added:
                                logger.debug(f"  + Added ({len(newly_added)} items): {newly_added}")
                            if newly_removed:
                                logger.debug(f"  - Removed ({len(newly_removed)} items): {newly_removed}")

                            # add to output array
                            output_changes.append({
                                "date": dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "list_name": list_name,
                                "added": list(newly_added),
                                "removed": list(newly_removed)
                            })

                        else:
                            logger.debug(f"No changes in {list_name}.")
                    else:
                        logger.debug(f"Initial state loaded for {list_name} ({len(current_items)} items).")

                # Set current state as previous for the next iteration
                previous_states[list_name] = current_items
                
            else:
                logger.warning(f"List {list_name} not found in folder {folder}.")

    with open(output_file, 'w') as f:
        json.dump(output_changes, f, indent=4)
    logger.debug(f"Output changes saved to {output_file}")  

    return output_changes

if __name__ == "__main__":
    fetch_webprivacy(START_DATE, END_DATE, OUTPUT_FILE)