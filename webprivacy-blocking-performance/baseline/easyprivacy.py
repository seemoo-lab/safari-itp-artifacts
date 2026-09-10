import logging
import os
import tldextract

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("EasyPrivacyBaseline")

def read_lines(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    return lines

def process_list(lines: list):
    rules = []
    for line in lines:
        line = line.strip()
        if line.startswith("!") or not line:
            continue
        rules.append(line)
    return rules

def fetch_domains_from_lists(src_dir: str) -> list:

    lists = [list for list in os.listdir(src_dir) if list.endswith(".txt")]
    
    all_rules = []
    for list in lists:
        file_path = os.path.join(src_dir, list)
        lines = read_lines(file_path)
        rules = process_list(lines)
        all_rules.extend(rules)
        logger.debug(f"Processed {len(rules)} rules from {list}")    
    
    # count rules that start with ||
    domain_rules = [rule for rule in all_rules if rule.startswith("||")]
    
    # filter out same domains under tldextract same top_domain_under_public_suffix
    shared_extractor = tldextract.TLDExtract()
    unique_domains = set()
    for rule in domain_rules:
        domain = rule[2:] #.split("/")[0].split(":")[0]
        ext = shared_extractor(domain)
        registrable_domain = ext.top_domain_under_public_suffix
        unique_domains.add(registrable_domain)

    return unique_domains

if __name__ == "__main__":
    fetch_domains_from_lists("./baseline/easyprivacy")
