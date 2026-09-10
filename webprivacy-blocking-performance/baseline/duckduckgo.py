import logging
import json

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("WebPrivacyBaseline")


def read_json_items(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data

def fetch_domains_from_items(src_dir: str) -> set:
    items_obj = read_json_items(src_dir)
    domains = set()

    # add all key values from trackers attribute
    for key in items_obj["trackers"].keys():
        domains.add(key)

    # add all from cnames
    for key, value in items_obj["cnames"].items():
        domains.add(key)
        domains.add(value)

    return domains


if __name__ == "__main__":
    fetch_domains_from_items("./baseline/duckduckgo/extension-tds.json")
