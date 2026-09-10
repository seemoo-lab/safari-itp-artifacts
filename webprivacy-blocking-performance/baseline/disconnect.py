import logging
import json

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("WebPrivacyBaseline")


def read_json_items(file_path):
    with open(file_path, "r") as f:
        items = json.load(f)
    items = items.get("categories", [])
    return items

def fetch_domains_from_items(src_dir: str) -> set:

    items_obj = read_json_items(src_dir) # consists of "NAME" -> ARRAY

    domains = set()
    for name, items in items_obj.items(): # Email, Analytics, ...
        logger.debug(f"Category: {name} has {len(items)} items")

        for inner in items:
            for inner_name, inner_items in inner.items():
                logger.debug(f"  Subcategory: {inner_name} has {len(inner_items)} items")

                domains.update(inner_items)

    return domains


if __name__ == "__main__":
    fetch_domains_from_items("./baseline/disconnect/services.json")
