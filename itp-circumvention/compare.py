import logging
import asyncio
import braveblock
import json
import concurrent.futures
import tldextract
from typing import List, Dict, Any, Optional

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CircumventionStats")


# Mapping for DuckDuckGo exception types to blocker resource types
DUCKDUCKGO_TYPE_MAP = {
    "main_frame": "document",
    "sub_frame": "subdocument",
    "stylesheet": "stylesheet",
    "script": "script",
    "image": "image",
    "font": "font",
    "object": "object",
    "xmlhttprequest": "xmlhttprequest",
    "ping": "ping",
    "media": "media",
    "websocket": "websocket",
    "csp_report": "other",
    "other": "other",
}

INPUT_EVIDENCE = "itp_purge_cookie_downgrade_evidence.json"
OUTPUT_FILE = "exfiltration_blocklist_matches.json"
MAX_WORKERS = 8

def read_data(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def read_file(path: str) -> List[str]:
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

tld_extractor = tldextract.TLDExtract()

def registrable_domain(host: str) -> str:
    """eTLD+1 for a hostname or URL, e.g. 'sub.example.co.uk' -> 'example.co.uk'."""
    ext = tld_extractor(host)
    return ext.top_domain_under_public_suffix

def _map_types(types: List[str]) -> List[str]:
    return [DUCKDUCKGO_TYPE_MAP.get(t, t) for t in types]

def _positive_options(domains: Optional[List[str]], types: Optional[List[str]]) -> str:
    """
    'domain=d1|d2,script,image' -> filter only applies when site domain is
    d1 OR d2 AND request type is script OR image. This is how ABP option
    categories combine (AND across categories, OR within a category), which
    matches the TDS rule: "if exceptions has both domains and types, both
    must match."
    """
    parts = []
    if domains:
        parts.append("domain=" + "|".join(domains))
    if types:
        parts.extend(_map_types(types))
    return ",".join(parts)

def _negated_block_filters(regex_filter: str, domains: Optional[List[str]], types: Optional[List[str]]) -> List[str]:
    """
    Build filter(s) that BLOCK everywhere except when domain AND type both
    match the exception (used when the tracker's overall default is
    "ignore" but this specific rule should block outside its exception).

    We want: block unless (domain in domains AND type in types)
           = block when (domain not in domains) OR (type not in types)

    A single ABP filter ANDs its option categories together, so it can't
    express that OR directly. Instead we emit up to two independent
    blocking filters -- since adblock-rust blocks on ANY matching filter,
    two filters covering the two disjuncts reproduce the OR.
    """
    filters = []
    if domains:
        filters.append(f"{regex_filter}$domain=" + "|".join(f"~{d}" for d in domains))
    if types:
        filters.append(f"{regex_filter}$" + ",".join(f"~{t}" for t in _map_types(types)))
    return filters


def parse_duckduckgo_list(path: str) -> List[str]:
    """
    Extract domain names from a DuckDuckGo TDS file.
    """

    with open(path, "r") as f:
        data = json.load(f)

    unique = set()

    for domain, entry in data["trackers"].items():
        default = entry.get("default", "block") # block or ignore
        rules = entry.get("rules", []) # empty or rules array

        # If default is blocked, then always block the domain
        if default == "block":
            unique.add(f"||{domain}^")

        # Iterate through rules if exist
        for rule in rules:

            pattern = rule.get("rule")
            if not pattern:
                continue
            
            regex_filter = f"/{pattern}/"
            action = rule.get("action", "block")  # default is block if not specified
            exceptions = rule.get("exceptions", {})
            exc_domains = exceptions.get("domains")
            exc_types = exceptions.get("types")

            if action == "ignore":
                # Unconditional "don't block" for this pattern for exceptions
                # are moot here since action already grants a blanket pass.
                if default == "block":
                    unique.add(f"@@{regex_filter}")
                # default == "ignore": already not blocked, nothing to add.
                continue

            # action resolves to "block" (explicit, or via the fallback)
            if exc_domains or exc_types:
                if default == "block":
                    # Base domain block already covers this pattern;
                    # carve out just the excepted domain/type combination.
                    options = _positive_options(exc_domains, exc_types)
                    unique.add(f"@@{regex_filter}${options}")
                else:
                    # default == "ignore": block this pattern everywhere
                    # except the excepted domain/type combination.
                    unique.update(_negated_block_filters(regex_filter, exc_domains, exc_types))
            else:
                if default == "ignore":
                    # No exceptions, rule matched -> block unconditionally.
                    unique.add(regex_filter)
                # default == "block", no exceptions: base domain block
                # above already covers this pattern -- nothing to add.


    return sorted(unique)

def parse_disconnect_list(path: str) -> List[str]:
    with open(path, "r") as f:
        data = json.load(f)
    data = data["categories"]

    tracking_categories = ["Advertising", "Analytics", "Social", "Content"] # there is no "Disconnect" category
    excluded_keys = {"performance", "dnt", "session-replay"}

    def domains_in(category):
        out = set()
        for entry in data[category]:
            for owner in entry:
                for key in entry[owner]:
                    if key not in excluded_keys:
                        out.update(entry[owner][key])
        return out

    # Advertising/Analytics/Social/Content/Disconnect (Level 2)
    tracking_domains = set()
    for cat in tracking_categories:
        tracking_domains |= domains_in(cat)

    # blocked cryptomining unconditionally
    cryptomining_domains = domains_in("Cryptomining")

    # only domains that are BOTH FingerprintingInvasive in tracking
    fp_domains = domains_in("FingerprintingInvasive") & tracking_domains

    unique = {
        f"||{d}^"
        for d in (tracking_domains | cryptomining_domains | fp_domains)
    }
    return sorted(unique)

def parse_disconnect_entitylist(path: str) -> Dict[str, str]:
    """
    Returns domain -> entity_name, combining 'properties' and 'resources'
    for every entity. Both lists matter: 'properties' tells us which entity
    owns the *site* the user is on, 'resources' tells us which entity owns
    the *tracker* domain being loaded.
    """
    with open(path, "r") as f:
        data = json.load(f)

    entities = data.get("entities", data)  # tolerate either shape
    domain_to_entity: Dict[str, str] = {}
    for entity_name, entry in entities.items():
        domains = set(entry.get("properties", [])) | set(entry.get("resources", []))
        for domain in domains:
            domain_to_entity[registrable_domain(domain)] = entity_name

    return domain_to_entity


def cleanup(data):
    for site in data:
        site['matching_cookies'] = [cookie for cookie in site['matching_cookies'] if cookie.get('cloakedRequest') is not None]
    return data

def analyze_items_parallel(
    items: list,
    blocklists: List[List[str]],
    max_workers: int,
    include_easyprivacy: bool,
) -> dict:
    results = {}
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=Worker.init,
        initargs=(blocklists, include_easyprivacy),
    ) as executor:
        future_to_item = {
            executor.submit(Worker.analyze, item): item for item in items
        }
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                matched_url = future.result()
            except Exception:
                logger.exception(f"Failed to analyze item {item.get('url', '<unknown>')}")
                continue
            if matched_url:
                results[matched_url] = True
    return results


class BlockerAnalyzer:

    def __init__(self, rules: List[List[str]], include_easyprivacy: bool = False):
        self.rule_blocker = braveblock.Adblocker(
            rules=[rule for sublist in rules for rule in sublist],
            include_easylist=False,
            include_easyprivacy=include_easyprivacy,
        )

    def check_blocked(self, item: dict) -> Optional[str]:
        source_url = item.get('url', '')
        for cookie in item.get('matching_cookies', []):
            for exfiltration_to_url in cookie.get('exfiltrated_to', []):
                if self.rule_blocker.check_network_urls(
                    url=exfiltration_to_url,
                    source_url=source_url,
                    request_type="",  # any type
                ):
                    return source_url
        return None

class Worker:

    analyzer: Optional[BlockerAnalyzer] = None

    @classmethod
    def init(cls, rules: List[List[str]], include_easyprivacy: bool):
        cls.analyzer = BlockerAnalyzer(rules=rules, include_easyprivacy=include_easyprivacy)

    @classmethod
    def analyze(cls, item: dict) -> Optional[str]:
        return cls.analyzer.check_blocked(item)


async def main():
    data = read_data(INPUT_EVIDENCE)
    data = cleanup(data)
    logger.info(f"Loaded {len(data)} crawl items from {INPUT_EVIDENCE}.")

    # iterate through all sites in data, remove all items from matching_cookies with cloakedRequest == true
    for site in data:
        site['matching_cookies'] = [cookie for cookie in site['matching_cookies'] if cookie.get('cloakedRequest') is not None]

    # prepare blocklists
    disconnect_blocklist = parse_disconnect_list("lists/disconnect_services.json")
    duckduckgo_blocklist = parse_duckduckgo_list("lists/duckduckgo_tracker_blocklist.json")
    blocklists = [disconnect_blocklist, duckduckgo_blocklist]

    logger.info(f"Analyzing {len(data)} crawl items across {MAX_WORKERS} worker processes.")
    loop = asyncio.get_running_loop()
    analysis_results = await loop.run_in_executor(
        None,
        lambda: analyze_items_parallel(data, blocklists, max_workers=MAX_WORKERS, include_easyprivacy=True),
    )
    logger.info(f"Analysis complete. Found {len(analysis_results)} circumvention cases to blocklist-endpoints.")

    # write all domains in result to a file (the whole object from data that matches the url)
    with open(OUTPUT_FILE, "w") as f:
        json.dump([site for site in data if site.get('url', '') in analysis_results], f, indent=2)
    logger.info(f"Results written to {OUTPUT_FILE}.")


if __name__ == "__main__":
    asyncio.run(main())
