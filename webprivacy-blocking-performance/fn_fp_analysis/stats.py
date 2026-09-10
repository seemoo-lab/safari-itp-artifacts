import json
import logging
import tldextract
import os
from collections import defaultdict
from urllib.parse import urlparse

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ListCoverageStats")

RESULTS_DIR = "results"
STATS_FILE = os.path.join(RESULTS_DIR, "blocker_extended_analysis_results.json")
SOURCE_FILE = os.path.join(RESULTS_DIR, "blocker_request_level_results.jsonl")

TOTAL_REQUESTS = 904568 # blocker_request_level_results.jsonl only contains requests blocked by at least one list
TOTAL_SITES_CRAWLED = 7218

TARGET = "SAFARI_PRIVATE_BROWSING"
REFERENCE_LISTS = ["DuckDuckGo", "EasyPrivacy", "Disconnect"]

tld_extractor = tldextract.TLDExtract()

def domain_path_key(req: object) -> tuple:
    parsed = urlparse(req["url"])
    template = parsed.path
    return (parsed.netloc, template, req["resource_type"])

def main():

    blocking_performance_analysis()

    request_map = {}
    raw_count = 0

    # Stream the JSONL file line by line to prevent memory overflow
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            req = json.loads(line)
            raw_count += 1
            
            # Deduplicate by domain_path_key per request on the fly
            key = (req["currentUrl"], domain_path_key(req))
            if key not in request_map:
                request_map[key] = req
            else:
                request_map[key]["blocked_by"] = list(
                    set(request_map[key]["blocked_by"]) | set(req["blocked_by"])
                )

    requests = list(request_map.values())
    logger.info(f"Deduplicated {raw_count} requests blocked by at least one blocker into {len(requests)} unique requests")

    false_negative_analysis(requests)
    false_positive_analysis(requests)
    

def blocking_performance_analysis():
    logger.info(f"Analyzing blocking performance.")

    with open(STATS_FILE, "r") as f:
        stats = json.load(f)

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        requests = [json.loads(line) for line in f if line.strip()]

    # Print stats for blocking performance of each reference list
    for name, stats in stats.items():
        if name in REFERENCE_LISTS:
            blocked_requests = stats["blocked_requests"]
            logger.info(f"{name} blocked {blocked_requests}/{TOTAL_REQUESTS} requests")

    # requests blocked by only FINGERPRINTING_SCRIPTS
    only_blocked_by_fingerprinting_scripts = [req for req in requests if "FINGERPRINTING_SCRIPTS" in req["blocked_by"]]
    logger.info(f"Found {len(only_blocked_by_fingerprinting_scripts)}/{TOTAL_REQUESTS} requests blocked by FINGERPRINTING_SCRIPTS")

    # domains in requests that are blocked by SAFARI_PRIVATE_BROWSING and TRACKING_DOMAINS
    only_blocked_by_target = [req for req in requests if TARGET in req["blocked_by"]]
    logger.info(f"Found {len(only_blocked_by_target)}/{TOTAL_REQUESTS} requests blocked by {TARGET}")

    # Contribution of TRACKING_DOMAINS to SAFARI_PRIVATE_BROWSING blocking
    only_tracking_domains = [req for req in only_blocked_by_target if "TRACKING_DOMAINS" in req["blocked_by"]]
    logger.info(f"  {len(only_tracking_domains)}/{len(only_blocked_by_target)} ({round(len(only_tracking_domains)/len(only_blocked_by_target)*100):.2f}%) blocked via TRACKING_DOMAINS")

    # Contribution of TRACKING_SUBNETS to SAFARI_PRIVATE_BROWSING blocking
    only_tracking_subnets = [req for req in only_blocked_by_target if "TRACKING_SUBNETS" in req["blocked_by"] and "TRACKING_DOMAINS" not in req["blocked_by"]]
    logger.info(f"  {len(only_tracking_subnets)}/{len(only_blocked_by_target)} ({round(len(only_tracking_subnets)/len(only_blocked_by_target)*100, 2):.2f}%) blocked via TRACKING_SUBNETS")

    # Contribution of URL_FILTER to SAFARI_PRIVATE_BROWSING blocking
    only_url_filter = [req for req in only_blocked_by_target if "URL_FILTER" in req["blocked_by"] and "TRACKING_DOMAINS" not in req["blocked_by"] and "TRACKING_SUBNETS" not in req["blocked_by"]]
    logger.info(f"  {len(only_url_filter)}/{len(only_blocked_by_target)} ({round(len(only_url_filter)/len(only_blocked_by_target)*100, 2):.2f}%) blocked via URL_FILTER")

    logger.info(f"Blocking performance analysis complete.")



def false_negative_analysis(requests):
    logger.info(f"Analyzing false negatives for {TARGET} against: {REFERENCE_LISTS}")

    ground_truth_one_reference = [req for req in requests if any(ref in req["blocked_by"] for ref in REFERENCE_LISTS)]
    ground_truth_two_references = [req for req in ground_truth_one_reference if sum(1 for ref in REFERENCE_LISTS if ref in req["blocked_by"]) >= 2]
    ground_truth_all_references = [req for req in ground_truth_two_references if sum(1 for ref in REFERENCE_LISTS if ref in req["blocked_by"]) >= 3]

    # Find requests not blocked by target but blocked by at least one reference list
    not_blocked_by_target = [req for req in ground_truth_one_reference if TARGET not in req["blocked_by"]]
    logger.info(f"Found {len(not_blocked_by_target)}/{len(ground_truth_one_reference)} requests not blocked by {TARGET} but blocked by >=1 reference list")
    logger.info(f"Resulting FNR: {len(not_blocked_by_target)}/{len(ground_truth_one_reference)} ({round(len(not_blocked_by_target)/len(ground_truth_one_reference)*100):d}%)")

    # Find requests not blocked by target but blocked by at least two reference lists
    blocked_by_two_or_more = [req for req in ground_truth_two_references if TARGET not in req["blocked_by"]]
    logger.info(f"Found {len(blocked_by_two_or_more)}/{len(ground_truth_two_references)} requests not blocked by {TARGET} but blocked by >=2 reference lists")
    logger.info(f"Resulting FNR: {len(blocked_by_two_or_more)}/{len(ground_truth_two_references)} ({round(len(blocked_by_two_or_more)/len(ground_truth_two_references)*100):d}%)")

    # Find requests not blocked by target but blocked by all three reference lists
    blocked_by_all_three = [req for req in ground_truth_all_references if TARGET not in req["blocked_by"]]
    logger.info(f"Found {len(blocked_by_all_three)}/{len(ground_truth_all_references)} requests not blocked by {TARGET} but blocked by all three reference lists")
    logger.info(f"Resulting FNR: {len(blocked_by_all_three)}/{len(ground_truth_all_references)} ({round(len(blocked_by_all_three)/len(ground_truth_all_references)*100):d}%)")


    # Group requests by domain, keeping the raw URLs that map to each templated key
    domain_to_grouped_urls = defaultdict(lambda: defaultdict(set))
    domain_to_sites = defaultdict(set)
    missed_domains = defaultdict(int)

    for req in blocked_by_all_three:
        domain = tld_extractor(req["url"]).top_domain_under_public_suffix
        parsed = urlparse(req["url"])
        template_key = domain_path_key(req)
        missed_domains[domain] += 1
        domain_to_grouped_urls[domain][template_key].add(f"{parsed.netloc}{parsed.path}")
        domain_to_sites[domain].add(req["currentUrl"])


    # Site-level exposure: how many distinct sites have >=1 unblocked-but-flagged request?
    sites_leak = {req["currentUrl"] for req in blocked_by_all_three}
    logger.info(
        f"Sites with >=1 unblocked tracker: "
        f"{len(sites_leak)}/{TOTAL_SITES_CRAWLED} ({len(sites_leak)/TOTAL_SITES_CRAWLED*100:.2f}%)"
    )

    # Per-domain site coverage
    for domain, count in sorted(missed_domains.items(), key=lambda x: x[1], reverse=True)[:5]:
        n_sites = len(domain_to_sites[domain])
        logger.info(f"  {domain}: {count} requests, {n_sites}/{TOTAL_SITES_CRAWLED} sites")

    logger.info(f"False positive analysis complete.")

def false_positive_analysis(requests):
    logger.info(f"Analyzing false positives for {TARGET} against: {REFERENCE_LISTS}")

    # requests that are only blocked by target but not any reference list
    only_blocked_by_target = [req for req in requests if TARGET in req["blocked_by"] and not any(ref in req["blocked_by"] for ref in REFERENCE_LISTS)]
    logger.info(f"Only blocked by {TARGET}: {len(only_blocked_by_target)}/{len(requests)}")

    # Site-level exposure: how many distinct sites have a block by target but not any reference list?
    sites_leak = {req["currentUrl"] for req in only_blocked_by_target}
    logger.info(
        f"Sites with >=1 unblocked tracker: "
        f"{len(sites_leak)}/{TOTAL_SITES_CRAWLED}"
    )

    # Group requests by domain, keeping the raw URLs that map to each templated key
    domain_to_grouped_urls = defaultdict(lambda: defaultdict(set))
    domain_to_sites = defaultdict(set)
    for req in only_blocked_by_target:
        domain = tld_extractor(req["url"]).top_domain_under_public_suffix
        parsed = urlparse(req["url"])
        template_key = domain_path_key(req)
        domain_to_grouped_urls[domain][template_key].add(f"{parsed.netloc}{parsed.path}")
        domain_to_sites[domain].add(req["currentUrl"])

    # Per-domain site coverage
    for domain, grouped_urls in sorted(domain_to_grouped_urls.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        n_sites = len(domain_to_sites[domain])
        logger.info(f"  {domain}: {len(grouped_urls)} requests, {n_sites}/{TOTAL_SITES_CRAWLED} sites")

    logger.info(f"False negative analysis complete.")
    
if __name__ == "__main__":
    main()