import logging
import json
import os
import tldextract

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("WebPrivacyBaseline")

PARAM_LISTS = ["QUERY_PARAM.json", "PARAMETER_RULES_EXCEPTIONS.json"]
URL_LISTS = ["FINGERPRINTING_SCRIPTS.json", "RESOURCE_MONITOR_URLS.json", "TRACKING_DOMAINS.json", "TRACKING_SUBNETS.json", "URL_FILTER.json"]

def read_json_items(file_path):
    with open(file_path, "r") as f:
        items = json.load(f)
    items = items.get("additions", [])
    return items
    
def process_resource_monitor_rule(rule: str):
    data = json.loads(rule)
    action = data.get("action", {}).get("type", "")
    trigger = data.get("trigger", {})
    logger.debug(f"Processed resource monitor rule: action={action}, trigger={trigger}")
    return {
        "action": action,
        "trigger": trigger
    }

def process_list(lines: list):
    rules = []
    for line in lines:
        line = line.strip()
        if line.startswith("!") or not line:
            continue
        rules.append(line)
    return rules

def fetch_counts(folder_path: str):
    
    lists = [list for list in os.listdir(folder_path)]
    logger.debug(f"Found {len(lists)} lists in {folder_path}")

    shared_extractor = tldextract.TLDExtract()

    list_content = {}
    for list in lists:
        content = read_json_items(os.path.join(folder_path, list))
        list_content[list] = content
        logger.debug(f"Read {len(content)} items from {list}")

    # remove all comments from RESOURCE_MONITOR_URLS
    list_content["RESOURCE_MONITOR_URLS.json"] = [item for item in list_content["RESOURCE_MONITOR_URLS.json"] if not item.startswith("#")]

    # process RESOURCE_MONITOR_URLS.json rules
    resource_monitor_rules = []
    for item in list_content["RESOURCE_MONITOR_URLS.json"]:
        try:
            rule = process_resource_monitor_rule(item)
            resource_monitor_rules.append(rule)
        except Exception as e:
            logger.warning(f"Failed to process rule in RESOURCE_MONITOR_URLS.json: {item} with error: {e}")
    logger.debug(f"Processed {len(resource_monitor_rules)} rules from RESOURCE_MONITOR_URLS")

    # count all rules
    count = 0
    for list in lists:
        count += len(list_content[list])
    logger.debug(f"Found {count} rules among all WebPrivacy lists")

    # in URL_FILTER.json, find all unique domains
    unique_domains = set()
    for item in list_content["URL_FILTER.json"]:
        parts = item.split(" ")
        if not parts:
            continue
            
        raw_url = parts[0]
        domain = raw_url.split("\\/")[0].replace('\\.', '.')
        unique_domains.add(domain)
    logger.debug(f"Found {len(unique_domains)} unique domains in URL_FILTER")

    # find unique entities in TRACKING_DOMAINS.json
    unique_tracking_domains = set()
    for item in list_content["TRACKING_DOMAINS.json"]:
        entity = item.split(";")[0]
        unique_tracking_domains.add(entity)
    logger.debug(f"Found {len(unique_tracking_domains)} unique tracking domains in TRACKING_DOMAINS")

    unique_subnets = set()
    for item in list_content["TRACKING_SUBNETS.json"]:
        subnet = item.split(";")[0]
        unique_subnets.add(subnet)
    logger.debug(f"Found {len(unique_subnets)} unique subnets in TRACKING_SUBNETS")

    # count url parameter rules
    parameter_rule_count = 0
    for item in list_content["QUERY_PARAM.json"]:
        parameter_rule_count += 1
    logger.debug(f"Found {parameter_rule_count} URL parameters in QUERY_PARAM")

    # FINGERPRINTING_SCRIPTS
    unique_fingerprinting_scripts = set()
    for item in list_content["FINGERPRINTING_SCRIPTS.json"]:
        unique_fingerprinting_scripts.add(item)
    logger.debug(f"Found {len(unique_fingerprinting_scripts)} unique fingerprinting scripts in FINGERPRINTING_SCRIPTS")

    # RESTRICTED_OPENER_DOMAINS
    unique_restricted_opener_domains = set()
    for item in list_content["RESTRICTED_OPENER_DOMAINS.json"]:
        unique_restricted_opener_domains.add(item)
    logger.debug(f"Found {len(unique_restricted_opener_domains)} unique restricted opener domains in RESTRICTED_OPENER_DOMAINS.json")

    # find unique domains
    unique_entities = set()
    for item in unique_tracking_domains:
        ext = shared_extractor(item)
        registrable_domain = ext.top_domain_under_public_suffix
        unique_entities.add(registrable_domain)
    for item in unique_domains:
        ext = shared_extractor(item)
        registrable_domain = ext.top_domain_under_public_suffix
        unique_entities.add(registrable_domain)
    logger.debug(f"Found {len(unique_entities)} unique entities across TRACKING_DOMAINS, FINGERPRINTING_SCRIPTS and URL_FILTER")

    return {
        "ALL_RULES": count,
        "FINGERPRINTING_SCRIPTS_DOMAINS": len(unique_fingerprinting_scripts),
        "ATFP_DOMAINS": len(unique_entities),
        "TRACKING_SUBNETS": len(unique_subnets),
        "QUERY_PARAM": parameter_rule_count,
    }

if __name__ == "__main__":
    data = fetch_counts("./baseline/webprivacy")
    logger.info(f"WebPrivacy Baseline Counts: {data}")
