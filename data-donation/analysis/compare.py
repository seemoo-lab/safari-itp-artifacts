import logging
import json
import tldextract
from typing import Counter, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CompareAnalysis")

INPUT_PREVALENT = "classified_domains.txt"
INPUT_BOUNCE_HUBS = "bounce_hubs.txt"

def read_file(path: str) -> List[str]:
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def parse_disconnect_list(path: str) -> List[str]:

    with open(path, "r") as f:
        items = json.load(f)
    categories = items.get("categories", [])

    domains = set()
    for name, items in categories.items(): # Email, Analytics, ...
        logger.debug(f"Category: {name} has {len(items)} items")

        # "Acoustic": {"https://www.acoustic.com/": [...], ...}
        for inner in items:
            for inner_name, inner_items in inner.items():
                logger.debug(f"  Subcategory: {inner_name} has {len(inner_items)} items")

                domains.update(inner_items)
    
    return sorted(domains)

def parse_peter_lowes_list(path: str) -> List[str]:

    content = read_file(path)

    # iterate over lines, skip lines starting with #
    domains = set()
    for line in content:
        if line.startswith("#"):
            continue
            
        # strip leading localhost IP
        parts = line.split()
        if len(parts) >= 2:
            domains.add(parts[1].strip())

    return sorted(domains)

def parse_duckduckgo_list(path: str) -> List[str]:
    
    with open(path, "r") as f:
        items = json.load(f)
    domains_obj = items.get("domains", [])

    domains = set(domains_obj.keys())
    return sorted(domains)


def main():

    # ITP donations
    file_to_use = INPUT_BOUNCE_HUBS # or INPUT_PREVALENT
    prevalent_domains = set(read_file(file_to_use))
    logger.info(f"Read {len(prevalent_domains)} prevalent domains from {file_to_use}")

    # Disconnect tracking protection list
    # https://disconnect.me/trackerprotection
    disconnect_domains = parse_disconnect_list("./analysis/lists/disconnect_services.json")
    logger.info(f"Parsed {len(disconnect_domains)} unique domains from Disconnect")

    # Peter Lowe's ad and tracking server blocklist
    # https://pgl.yoyo.org/adservers/
    peter_lowes_domains = parse_peter_lowes_list("./analysis/lists/peter_lowe_list.txt")
    logger.info(f"Parsed {len(peter_lowes_domains)} unique domains from Peter Lowe")

    # DuckDuckGo tracker blocklists (built with DuckDuckGo's tracker radar)
    # https://github.com/duckduckgo/tracker-blocklists
    duckduckgo_domains = parse_duckduckgo_list("./analysis/lists/duckduckgo_tracker_blocklist.json")
    logger.info(f"Parsed {len(duckduckgo_domains)} unique domains from DuckDuckGo")

    # for each domain in each list, apply 
    shared_extractor = tldextract.TLDExtract(cache_dir=".tld_cache")
    for domain in disconnect_domains:
        ext = shared_extractor(domain)
        registered_domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        disconnect_domains.remove(domain)
        disconnect_domains.append(registered_domain)

    for domain in peter_lowes_domains:
        ext = shared_extractor(domain)
        registered_domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        peter_lowes_domains.remove(domain)
        peter_lowes_domains.append(registered_domain)

    for domain in duckduckgo_domains:
        ext = shared_extractor(domain)
        registered_domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        duckduckgo_domains.remove(domain)
        duckduckgo_domains.append(registered_domain)

    disconnect_domains = set(disconnect_domains)
    peter_lowes_domains = set(peter_lowes_domains)
    duckduckgo_domains = set(duckduckgo_domains)

    # statistics
    statistics = Counter()
    for domain in prevalent_domains:
        in_disconnect = domain in disconnect_domains
        in_peter_lowes = domain in peter_lowes_domains
        in_duckduckgo = domain in duckduckgo_domains

        if in_disconnect and in_peter_lowes and in_duckduckgo:
            statistics["all_three"] += 1
        elif in_disconnect and in_peter_lowes:
            statistics["disconnect_peter_lowes"] += 1
        elif in_disconnect and in_duckduckgo:
            statistics["disconnect_duckduckgo"] += 1
        elif in_peter_lowes and in_duckduckgo:
            statistics["peter_lowes_duckduckgo"] += 1
        elif in_disconnect:
            statistics["disconnect_only"] += 1
        elif in_peter_lowes:
            statistics["peter_lowes_only"] += 1
        elif in_duckduckgo:
            statistics["duckduckgo_only"] += 1
        else:
            statistics["none"] += 1

        # in at least one of the lists
        if in_disconnect or in_peter_lowes or in_duckduckgo:
            statistics["at_least_one"] += 1

    logger.info("Comparing prevalent domains with other lists:")
    total = len(prevalent_domains)
    for category, count in statistics.items():
        pct = (count / total) * 100 if total > 0 else 0
        logger.info(f"  {category}: {count} ({pct:.2f}%)")

    # list some examples of none
    none_examples = [domain for domain in prevalent_domains if domain not in disconnect_domains and domain not in peter_lowes_domains and domain not in duckduckgo_domains]
    logger.info(f"Examples of prevalent domains not in any list (showing up to 20):")
    for domain in none_examples[:20]:
        logger.info(f"  {domain}")

if __name__ == "__main__":
    main()