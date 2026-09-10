import argparse
import io
import json
import logging
import sys
import requests
import pandas as pd

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dataset")

# Constants
TRANCO_URL = "https://tranco-list.eu/download/{list_id}/{top_k}"
TRANCO_LATEST_API = "https://tranco-list.eu/api/lists/date/latest"
TOP_K = 10_000
OUTFILE = "top-10k.csv"


def fetch_url(url: str) -> bytes:
    logger.debug("Fetching %s", url)
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP error fetching %s: %s", url, e)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logger.error("Failed to reach %s: %s", url, e)
        sys.exit(1)
    return resp.content

def resolve_list_id() -> str:
    body = fetch_url(TRANCO_LATEST_API)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Could not parse the latest-list API response as JSON.")
        sys.exit(1)
    list_id = data.get("list_id")
    if not list_id:
        logger.error("Latest-list API response did not contain a list_id.")
        sys.exit(1)
    return list_id

def download_tranco_csv(list_id: str, top_k: int) -> bytes:
    url = TRANCO_URL.format(list_id=list_id, top_k=top_k)
    return fetch_url(url)

def write_csv(raw_csv: bytes, top_k: int, outfile: str) -> int:
    df = pd.read_csv(io.BytesIO(raw_csv), header=None, names=["rank", "domain"])
    df = df.head(top_k)
 
    if df.empty:
        logger.error("Downloaded CSV had no rows to write.")
        sys.exit(1)
 
    df.to_csv(outfile, index=False, header=False)
 
    return len(df)


if __name__ == "__main__":

    # parse CLI arguments
    parser = argparse.ArgumentParser(description="Create dataset of top K domains from Tranco.")
    parser.add_argument("--list", type=str, default="", help="tranco list identifier.")
    parser.add_argument("--k", type=int, default=TOP_K, help="number of top domains to include.")
    parser.add_argument("--out", type=str, default=OUTFILE, help="output CSV file.")
    args = parser.parse_args()

    if args.k <= 0:
        logger.error("--k must be a positive integer.")
        sys.exit(1)

    list_id = args.list or resolve_list_id()
    logger.info("Using Tranco list ID: %s", list_id)

    logger.info("Downloading top %d domains...", args.k)
    raw_csv = download_tranco_csv(list_id, args.k)

    count = write_csv(raw_csv, args.k, args.out)
    logger.info("Wrote %d rows to %s", count, args.out)