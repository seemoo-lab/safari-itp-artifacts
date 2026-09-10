import json
import logging
import asyncio
import re
import braveblock
import tldextract
import ipaddress
import ijson
import threading
import os
import multiprocessing as mp
import concurrent.futures
from collections import defaultdict
from typing import List, Optional, Dict

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ListCoverageAnalyzer")


LOCAL_CRAWL = "/data/crawl_webkit_1.jsonl"

RESULTS_DIR = "results"
STATS_FILE = os.path.join(RESULTS_DIR, "blocker_extended_analysis_results.json")
SOURCE_FILE = os.path.join(RESULTS_DIR, "blocker_request_level_results.jsonl")

# Load environment variables
MAX_WORKERS = 8

# Mapping from URL_FILTER types to blocker resource types
URL_FILTER_TYPE_MAP = {
    "document": "document",
    "image": "image",
    "script": "script",
    "xhr": "xmlhttprequest",
    "fetch": "xmlhttprequest",
    "ping": "ping",
    "beacon": "ping",
    "other": "other",
    "stylesheet": "stylesheet",
    "eventsource": "other",
    "font": "font",
}

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


tld_extractor = tldextract.TLDExtract(suffix_list_urls=())

def registrable_domain(host: str) -> str:
    """eTLD+1 for a hostname or URL, e.g. 'sub.example.co.uk' -> 'example.co.uk'."""
    ext = tld_extractor(host)
    return ext.top_domain_under_public_suffix

def check_ip_in_subnets(dns_record: Dict[str, List[str]], subnets: List[str]) -> bool:
    """
    Checks if any IPv4 or IPv6 addresses in a DNS record match a list of subnets.
    
    Args:
        dns_record: A dictionary containing 'A' and 'AAAA' keys with lists of IP strings.
        subnets: A list of IPv4 and IPv6 subnet strings.
        
    Returns:
        True if at least one IP address falls within at least one subnet, False otherwise.
    """
    
    # Convert subnet strings to ipaddress network objects
    network_objects = []
    for subnet in subnets:
        try:
            network_objects.append(ipaddress.ip_network(subnet, strict=False))
        except ValueError:
            pass # Ignore invalid subnets
            
    # Combine A (IPv4) and AAAA (IPv6) records into a single list
    ip_strings = dns_record.get("A", []) + dns_record.get("AAAA", [])
    
    # Check each IP against all subnets
    for ip_str in ip_strings:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            
            # Using the `in` operator to check if IP is in the network
            if any(ip_obj in network for network in network_objects):
                return True
                
        except ValueError:
             pass # Ignore invalid IP addresses
             
    return False

def _map_types(types: List[str]) -> List[str]:
    """Map DuckDuckGo exception types to blocker resource types."""
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
    """Extract domain names from a DuckDuckGo TDS file."""

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

def parse_url_filter_list(path: str) -> List[str]:
    """
    Parses a URL_FILTER.json export into a list of braveblock-compatible
    filter rules. Plain URLs pass through as literal filters, e.g.
    "||example.com^$script,image". Entries containing regex syntax are
    wrapped as slash-delimited regex filters instead, preserving their
    escaping so `.` and `+` keep their regex meaning.
    """
    with open(path, "r") as f:
        data = json.load(f)

    rules = []
    for raw_line in data.get("additions", []):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split(" ", 1)
        url = parts[0].strip()
        types = []

        if len(parts) > 1:
            type_part = parts[1].strip()
            for t in type_part.split(","):
                t = t.strip()
                if t in URL_FILTER_TYPE_MAP:
                    types.append(URL_FILTER_TYPE_MAP[t])

        # detect genuine regex syntax rather than stripping backslashes —
        # stripping destroys the escaping that gives .+ its regex meaning
        if re.search(r'\\.|\.\+|\.\*', url):
            pattern = f"/{url}/"
        else:
            pattern = url

        rule = f"{pattern}${','.join(types)}" if types else pattern
        rules.append(rule)

    return rules

def parse_fingerprinting_list(path: str) -> List[str]:

    with open(path, "r") as f:
        data = json.load(f)

    domains = set()
    for raw_line in data.get("additions", []):
        line = raw_line.strip()
        if not line:
            continue

        domains.add(f"||{line}^")

    return domains

def parse_tracking_domains_list(path: str) -> List[str]:
    """
    Parses a TRACKING_DOMAINS.json export into a list of domain strings.

    Replicates the filtering logic of WebPrivacy::createTrackerDomainNamesData:
    - fields[3] must equal "1" to be included (skips all "2" value entries)
    - For 5-field rows, the last field must equal "1", otherwise skipped
    - For 4-field rows, fields[3] must equal "1" for the row to be included
    """
    with open(path, "r") as f:
        data = json.load(f)

    domains = []
    for raw_line in data.get("additions", []):
        line = raw_line.strip()
        if not line:
            continue

        fields = line.split(";")
        count = len(fields)

        # fields[3] must equal "1" to be included (skips all "2" value entries)
        host = fields[0].strip()
        if not host:
            continue

        # For 5-field rows, the last field must equal "1", otherwise row skipped
        if count == 5 and fields[4] != "1":
            continue

        # For 4-field rows, fields[3] must equal "1" for the row to be included at all
        if fields[3] != "1":
            continue

        domains.append(f"||{host}^")

    return domains

def parse_tracking_subnets_list(path: str) -> List[str]:
    """
    Parses a TRACKING_SUBNETS.json export into a list of subnet strings.
    """
    with open(path, "r") as f:
        data = json.load(f)

    domains = []
    for raw_line in data.get("additions", []):
        line = raw_line.strip()
        if not line:
            continue

        # subnet is first part before semicolon
        subnet = line.split(";")[0].strip()
        if subnet:
            domains.append(subnet)
            
    return domains

def parse_query_param_list(path: str) -> List[str]:
    """
    Parses a QUERY_PARAM.json export into a list of braveblock-compatible
    filter rules. Each rule is a slash-delimited regex matching the query
    parameter. Entries with a single token match the param on any host,
    using a shared, pre-validated pattern template. Entries with two
    tokens ("<param> <host>") only match the param when the request's
    host is that host, via a custom per-entry regex.
    """

    with open(path, "r") as f:
        data = json.load(f)

    rules = []
    for raw_line in data.get("additions", []):
        item = raw_line.strip().strip('",')
        if not item:
            continue

        tokens = item.split()
        param = tokens[0]
        host = tokens[1] if len(tokens) > 1 else None

        rule = f"||{host}/*{param}=" if host else f"{param}="
        rules.append(rule)

    return rules

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


class BlockerWorker:
    
    blockers: dict = {}
    out_queue: mp.Queue = None

    @classmethod
    def init(cls, queue: mp.Queue) -> None:
        """
        Runs exactly once per worker process.
        Workers load the rules from disk themselves to bypass IPC serialization overhead.
        """
        cls.out_queue = queue
        
        cls.blockers = {
            "Disconnect": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_disconnect_list("./fn_fp_analysis/lists/disconnect_services.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
                "entity_map": parse_disconnect_entitylist("./fn_fp_analysis/lists/disconnect_entitylist.json"),
            },
            "DuckDuckGo": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_duckduckgo_list("./fn_fp_analysis/lists/duckduckgo_tracker_blocklist.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
            },
            "EasyPrivacy": {
                "rule_blocker": braveblock.Adblocker(
                    rules=[],
                    include_easylist=False,
                    include_easyprivacy=True,
                ),
            },

            "FINGERPRINTING_SCRIPTS": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_fingerprinting_list("./fn_fp_analysis/lists/FINGERPRINTING_SCRIPTS.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
            },
            "TRACKING_DOMAINS": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_tracking_domains_list("./fn_fp_analysis/lists/TRACKING_DOMAINS.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
            },
            "TRACKING_SUBNETS": {
                "subnet_blocker": parse_tracking_subnets_list("./fn_fp_analysis/lists/TRACKING_SUBNETS.json"),
            },
            "URL_FILTER": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_url_filter_list("./fn_fp_analysis/lists/URL_FILTER.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
            },
            "SAFARI_PRIVATE_BROWSING": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_tracking_domains_list("./fn_fp_analysis/lists/TRACKING_DOMAINS.json") + parse_url_filter_list("./fn_fp_analysis/lists/URL_FILTER.json"),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
                "subnet_blocker": parse_tracking_subnets_list("./fn_fp_analysis/lists/TRACKING_SUBNETS.json"),
            },
            "SAFARI_ALL": {
                "rule_blocker": braveblock.Adblocker(
                    rules=parse_tracking_domains_list("./fn_fp_analysis/lists/TRACKING_DOMAINS.json") + parse_url_filter_list("./fn_fp_analysis/lists/URL_FILTER.json") + list(parse_fingerprinting_list("./fn_fp_analysis/lists/FINGERPRINTING_SCRIPTS.json")),
                    include_easylist=False,
                    include_easyprivacy=False,
                ),
                "subnet_blocker": parse_tracking_subnets_list("./fn_fp_analysis/lists/TRACKING_SUBNETS.json"),
            }
            # Add back your WebPrivacy lists here using the same pattern
        }

    @classmethod
    def process_chunk(cls, chunk: list) -> dict:
        stats = {
            name: {
                "total_requests": 0,
                "blocked_requests": 0,
                "sites_with_any_block": 0,
                "blocked_by_resource_type": defaultdict(int),
                "blocked_by_subnet": 0,
                "blocked_by_rule": 0,
            }
            for name in cls.blockers
        }
        
        for item in chunk:
            current_url = item.get("currentUrl") or item.get("url")
            site_domain = registrable_domain(current_url) if current_url else None
            loaded_urls = item.get("loaded_urls", []) or []
            site_had_block = defaultdict(bool)

            for loaded in loaded_urls:
                url = loaded.get("url")
                if not url:
                    continue

                if site_domain and registrable_domain(url) == site_domain:
                    continue

                resource_type = loaded.get("resource_type", "other")
                dns_record = loaded.get("dns", {})
                blocked_by = []

                for name, blockers in cls.blockers.items():
                    stats[name]["total_requests"] += 1
                    blocked = False
                    
                    try:
                        if blockers.get("entity_map"):
                            resource_domain = registrable_domain(url)
                            site_entity = blockers.get("entity_map").get(site_domain)
                            resource_entity = blockers.get("entity_map").get(resource_domain)
                            if site_entity is not None and site_entity == resource_entity:
                                continue

                        if blockers.get("subnet_blocker"):
                            blocked = check_ip_in_subnets(dns_record, blockers["subnet_blocker"]) if dns_record else False
                            if blocked:
                                stats[name]["blocked_by_subnet"] += 1

                        if not blocked and blockers.get("rule_blocker"):
                            blocked = blockers["rule_blocker"].check_network_urls(
                                url=url,
                                source_url=current_url,
                                request_type=resource_type,
                            )
                            if blocked:
                                stats[name]["blocked_by_rule"] += 1

                    except Exception as e:
                        logger.error(f"Worker evaluation failed for {url}: {e}")
                        blocked = False

                    if blocked:
                        stats[name]["blocked_requests"] += 1
                        stats[name]["blocked_by_resource_type"][resource_type] += 1
                        site_had_block[name] = True
                        blocked_by.append(name)

                # Send directly to the writer thread instead of keeping in memory
                if len(blocked_by) > 0:
                    cls.out_queue.put({
                        "currentUrl": current_url,
                        "url": url,
                        "resource_type": resource_type,
                        "blocked_by": blocked_by,
                    })

            for name in stats:
                if site_had_block[name]:
                    stats[name]["sites_with_any_block"] += 1

        for name in stats:
            stats[name]["blocked_by_resource_type"] = dict(stats[name]["blocked_by_resource_type"])

        return stats

def stream_and_chunk_data(filepath: str, chunk_size: int = 100):
    chunk = []
    with open(filepath, "rb") as f:
        for item in ijson.items(f, "", multiple_values=True):
            if item.get("skipped") is None and item.get("status") == "success":
                chunk.append({
                    "currentUrl": item.get("currentUrl"),
                    "loaded_urls": item.get("loaded_urls", []),
                    "dns": item.get("dns", {})
                })
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
    if chunk:
        yield chunk

def output_writer(queue: mp.Queue, output_filename: str):
    """
    Background thread that listens to workers and writes results directly to disk.
    Uses JSON Lines (.jsonl) to prevent memory accumulation.
    """
    with open(output_filename, "w", encoding="utf-8") as f:
        while True:
            item = queue.get()
            if item == "DONE":
                break
            f.write(json.dumps(item) + "\n")

def _merge_stats(results: list[dict]) -> dict:
    merged = {}
    for chunk_stats in results:
        for name, stats in chunk_stats.items():
            if name not in merged:
                merged[name] = {
                    "total_requests": 0,
                    "blocked_requests": 0,
                    "sites_with_any_block": 0,
                    "blocked_by_resource_type": defaultdict(int),
                    "blocked_by_subnet": 0,
                    "blocked_by_rule": 0,
                }
            merged[name]["total_requests"] += stats["total_requests"]
            merged[name]["blocked_requests"] += stats["blocked_requests"]
            merged[name]["sites_with_any_block"] += stats["sites_with_any_block"]
            merged[name]["blocked_by_subnet"] += stats.get("blocked_by_subnet", 0)
            merged[name]["blocked_by_rule"] += stats.get("blocked_by_rule", 0)
            
            for r_type, count in stats["blocked_by_resource_type"].items():
                merged[name]["blocked_by_resource_type"][r_type] += count

    # Convert defaultdicts back to regular dicts for JSON serialization
    for name in merged:
        merged[name]["blocked_by_resource_type"] = dict(merged[name]["blocked_by_resource_type"])
        
    return merged

def analyze_crawl_items_parallel(filepath: str, max_workers: int = MAX_WORKERS) -> dict:
    
    manager = mp.Manager()
    queue = manager.Queue()
    
    # Start the background writer thread
    writer_thread = threading.Thread(
        target=output_writer, 
        args=(queue, SOURCE_FILE)
    )
    writer_thread.start()
    
    chunks = stream_and_chunk_data(filepath, chunk_size=100)
    all_stats = []

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=BlockerWorker.init,
        initargs=(queue,),
    ) as executor:
        for chunk_stats in executor.map(BlockerWorker.process_chunk, chunks):
            all_stats.append(chunk_stats)

    # Signal the writer thread to shut down
    queue.put("DONE")
    writer_thread.join()

    return _merge_stats(all_stats)

async def main():

    logger.info(f"Starting analysis across {MAX_WORKERS} workers.")
    
    loop = asyncio.get_running_loop()
    final_stats = await loop.run_in_executor(
        None,
        lambda: analyze_crawl_items_parallel(LOCAL_CRAWL, max_workers=MAX_WORKERS),
    )

    # Save stats
    with open(STATS_FILE, "w") as f:
        json.dump(final_stats, f, indent=2)

    logger.info("Analysis complete.")


if __name__ == "__main__":
    asyncio.run(main())