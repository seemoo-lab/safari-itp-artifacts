import requests
import urllib3
import json
import os
from argparse import ArgumentParser
from typing import List

# ignore ssl warnings as request uses apple-owned certs (= not trusted by default)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUTPUT_DIR = "output/"

AVAILABLE_LISTS = ["URL_FILTER", "STORAGE_ACCESS_USER_AGENT_STRING_QUIRKS", "STORAGE_ACCESS_PROMPT_QUIRKS", "QUERY_PARAM", "ALLOWED_QUERY_PARAM", "RESTRICTED_OPENER_DOMAINS", "FINGERPRINTING_SCRIPTS", "TRACKING_SUBNETS", "TRACKING_DOMAINS", "RESOURCE_MONITOR_URLS"]


DEFAULT_HEADERS = {
    "User-Agent": "com.apple.WebKit.Networking WebPrivacy%20Daemon (unknown version) CFNetwork/3860.100.1 Darwin/25.0.0",
    "X-HTTP-Method-Override": "POST",
    "Content-Type": "application/json",
    "X-API-Version": "1.5.0-prod.1682973469258.a186",
}

def request_list(type: str, state: str = None) -> List[object]:

    data = {
        "state": state if state else None,
        "remoteList": type,
        "client": {
            "clientVersion": "1",
            "clientId": "com.apple.WebKit.Networking"
        },
        "remoteListVersion": "v1"
    }
    response = requests.post(f"https://wps.apple.com/v1/getRemoteList", headers=DEFAULT_HEADERS, json=data, verify=False)
    response.raise_for_status()
    return response.content.decode("utf-8")

def write_file(name: str, data: List, output_dir: str = OUTPUT_DIR):

    # format json data
    json_data = json.loads(data)
    data = json.dumps(json_data, indent=4)

    # write json_data to file
    out_path = os.path.join(output_dir, f"{name}.json")
    with open(out_path, "w") as f:
        f.write(data)

def parse_lists_arg(lists_arg: str) -> List[str]:

    # check if argument is None
    if lists_arg is None:
        return AVAILABLE_LISTS

    # split by comma, return default if empty
    parts = [p.strip() for p in lists_arg.split(",") if p.strip()]

    # strip out parts that are not in list
    parts = [p for p in parts if p in AVAILABLE_LISTS]

    return parts if parts else AVAILABLE_LISTS

def main():

    parser = ArgumentParser(description="Fetch Apple WebPrivacy lists and save to files.")
    parser.add_argument("--output_dir", "-o", dest="output_dir", default=OUTPUT_DIR,
                        help=f"Directory to write output files (default: {OUTPUT_DIR})")
    parser.add_argument("--lists", "-l", dest="lists", default=None,
                        help="Comma-separated list of remote lists to fetch, or path to a JSON file containing an array of list names. If omitted, the default AVAILABLE_LISTS is used.")

    args = parser.parse_args()

    output_dir = args.output_dir
    lists = parse_lists_arg(args.lists)

    # ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # loop through available lists and fetch each one
    for name in lists:
        print(f"Fetching {name}...")
        tracking = request_list(name)
        write_file(name, str(tracking), output_dir=output_dir)
        print(f"Saved {name}.json")


if __name__ == "__main__":
    main()