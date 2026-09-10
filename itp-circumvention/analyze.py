import logging
import asyncio
import re
import urllib.parse
import base64
import json
import hashlib
import tldextract
import concurrent.futures
from datetime import datetime
from collections import defaultdict

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CircumventionAnalysis")

# Files
FIRST_CRAWL_FILE = "/data/crawl_webkit_1.jsonl"
SECOND_CRAWL_FILE = "/data/crawl_webkit_2.jsonl"
OUTPUT_FILE = "itp_purge_cookie_downgrade_evidence.json"

PROJECTION_FIELDS = [
    "url",
    "timestamp",
    "currentUrl",
    "cookies",
    "loaded_urls",
    "dns",
]

WORKER_TLD_EXTRACTOR = None

# Analysis parameters
MAX_WORKERS = 8
MIN_LENGTH = 8
MAX_DEPTH = 5
REGEX_IDENTIFIER = r'[a-zA-Z0-9_=\-\.]+'
IGNORE_COOKIES = {}

# takes two IPs as input (IPv4 or IPv6), performs the following checks:
# - if IPs differ in type (one is IPv4 and the other is IPv6) -> false
# - if both are same type, return true if 50% or more of the octets match, else false
def compare_ips(ip1: str, ip2: str) -> bool:
    # Check if both IPs are of the same type (IPv4 or IPv6)
    is_ip1_ipv4 = '.' in ip1
    is_ip2_ipv4 = '.' in ip2
    
    if is_ip1_ipv4 != is_ip2_ipv4:
        return False  # Different types, cannot be considered similar
    
    # Split IPs into octets
    octets1 = ip1.split('.' if is_ip1_ipv4 else ':')
    octets2 = ip2.split('.' if is_ip2_ipv4 else ':')
    
    # Count matching octets
    matching_octets = sum(1 for o1, o2 in zip(octets1, octets2) if o1 == o2)
    
    # Determine threshold for similarity (50% or more)
    threshold = len(octets1) / 2
    
    return matching_octets >= threshold

def build_dns_lookup(urls, shared_extractor):
    lookup = {}
    for entry in urls:
        entry_url = entry.get('url')
        entry_dns = entry.get('dns')
        if not entry_url or not entry_dns:
            continue
        fqdn = shared_extractor(entry_url).fqdn
        if fqdn and fqdn not in lookup:
            lookup[fqdn] = entry_dns
    return lookup

def filter_itp_persistant_cookies(state):
    original_cookies = state.get("cookies", [])
    cookies = [c for c in original_cookies if c.get('setVia', None) == 'server' or c.get('httpOnly', False)]
    cookies = [cookie for cookie in cookies if cookie.get('expires', -1) != -1]
    return cookies

def fully_decode(value):
    prev = None
    curr = value
    while prev != curr:
        prev = curr
        curr = urllib.parse.unquote_plus(curr)
    return curr

def extract_values_from_json(obj):
    values = []
    if isinstance(obj, dict):
        for v in obj.values():
            values.extend(extract_values_from_json(v))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(extract_values_from_json(item))
    elif isinstance(obj, (str, int, float)):
        values.append(str(obj))
    return values

def generate_signatures(cookie_list, ignore_cookies=None):
    if ignore_cookies is None:
        ignore_cookies = set()
        
    signatures = defaultdict(set)
    
    for cookie in cookie_list:
        name = cookie.get('name', '')
        if name in ignore_cookies:
            continue

        original_value = cookie.get('value', '')
        if not original_value:
            continue

        decoded_value = fully_decode(original_value)
        
        raw_parts = []
        try:
            parsed_json = json.loads(decoded_value)
            raw_parts.extend(extract_values_from_json(parsed_json))
        except json.JSONDecodeError:
            raw_parts.append(decoded_value)
            
        final_parts = set()
        for part in raw_parts:
            final_parts.add(part)
            splits = re.split(r'[._\-:;@|~]', part)
            final_parts.update(splits)
            
        for part in final_parts:
            if len(part) < 8: 
                continue
                
            if not heuristic_is_identifier(part):
                continue
            
            signatures[part].add(name)
            signatures[urllib.parse.quote(part)].add(name)
            
            if len(part) >= 16:
                try:
                    b64_val = base64.b64encode(part.encode('utf-8')).decode('utf-8')
                    signatures[b64_val].add(name)
                    signatures[b64_val.rstrip('=')].add(name)
                except: pass
                
                try:
                    md5_val = hashlib.md5(part.encode('utf-8')).hexdigest()
                    signatures[md5_val].add(name)
                except: pass
                
                try:
                    sha1_val = hashlib.sha1(part.encode('utf-8')).hexdigest()
                    signatures[sha1_val].add(name)
                except: pass

                try:
                    sha256_val = hashlib.sha256(part.encode('utf-8')).hexdigest()
                    signatures[sha256_val].add(name)
                except: pass
                
    return signatures

def find_exfiltrated_cookies(first_p_url, cookies_a, loaded_urls):
    persistent_sigs = generate_signatures(cookies_a, ignore_cookies=IGNORE_COOKIES)
    if not persistent_sigs:
        return []

    results = []

    for url_item in loaded_urls:
        if not url_item: continue
        
        url = url_item.get('url', '')
        try:
            url_decoded = urllib.parse.unquote(url)
        except:
            url_decoded = url

        post_data_decoded = ""
        try:
            post_data = url_item.get('post_data', '')
            post_data_decoded = urllib.parse.unquote(post_data)
        except:
            post_data_decoded = ""

        headers = url_item.get('headers', [])
        try:
            headers_decoded = [urllib.parse.unquote(header.get('value', '')) for header in headers]
        except:
            headers_decoded = headers

        shared_extractor = WORKER_TLD_EXTRACTOR
        if shared_extractor(url).top_domain_under_public_suffix == shared_extractor(first_p_url).top_domain_under_public_suffix:
           continue
            
        found_persistent = set()
        
        for sig, cookie_names in persistent_sigs.items():
            matched_sources = []
            if sig in url or sig in url_decoded:
                matched_sources.append("url")
            if sig in post_data_decoded:
                matched_sources.append("post_data")
            if any(sig in header for header in headers_decoded):
                matched_sources.append("header")
                
            if matched_sources:
                for c_name in cookie_names: 
                    for source in matched_sources:
                        found_persistent.add((c_name, sig, source))
                
        def filter_longest_match(matches):
            grouped = defaultdict(list)
            for m in matches:
                grouped[m[0]].append(m)
            return {max(v, key=lambda m: (len(m[1]), m[1], m[2])) for v in grouped.values()}
        
        found_persistent = filter_longest_match(found_persistent)

        if found_persistent:
            results.append({
                'url': url,
                'currentUrl': url_item.get('currentUrl', ''),
                'is3rd_party': True, 
                'matches': list(found_persistent),
            })

    return results

def heuristic_is_identifier(value, url = None):
    if not value:
        return False
    
    if len(value) < MIN_LENGTH:
        return False
        
    if not re.fullmatch(REGEX_IDENTIFIER, value):
        return False
    
    if re.fullmatch(r'^\d{10}$', value) and 1700000000 <= int(value) <= 2000000000:
        return False
    
    if value.startswith("www.") or value.startswith("http"):
        return False
    
    if re.fullmatch(r'^\d+\.\d+(\.\d+)?$', value):
        return False
    
    if url:
        shared_extractor = WORKER_TLD_EXTRACTOR
        if shared_extractor(url).domain in value:
            return False
        
    return True

def is_request_cloaked(main_dns, current_url, set_by_domain, dns_lookup):
    shared_extractor = WORKER_TLD_EXTRACTOR
    main_ext = shared_extractor(current_url).fqdn
    set_by_ext = shared_extractor(set_by_domain).fqdn

    if main_ext == set_by_ext:
        # The cookie is set by the same domain as the current URL, no cloaked
        return False, None

    dns_record = dns_lookup.get(set_by_ext)
    if dns_record is None:
        # No dns record collected during crawl (e.g., due to error)
        return None, None

    if main_dns:
        all_ips = dns_record.get("A", []) + dns_record.get("AAAA", [])
        main_dns_ips = main_dns.get("A", []) + main_dns.get("AAAA", [])
        for m_ip in main_dns_ips:
            for ip in all_ips:
                if compare_ips(m_ip, ip):
                    return False, dns_record

    return True, dns_record

def get_cookie_dict(exfiltrations):
    cookie_dict = {}
    destinations_dict = {}
                
    for exf in exfiltrations:
        req_url = exf.get('url', '')
        try:
            domain = req_url
        except Exception:
            domain = "unknown"

        for match in exf.get('matches', []):
            if len(match) >= 2:
                name, value = match[0], match[1]
                            
                if name not in cookie_dict:
                    cookie_dict[name] = set()
                cookie_dict[name].add(value)
                            
                if name not in destinations_dict:
                    destinations_dict[name] = set()
                if domain:
                    destinations_dict[name].add(domain)
                                
    return cookie_dict, destinations_dict

def analyze_single_url_task(task_data):
    url, before_state, after_state = task_data
    try:
        main_dns = before_state.get('dns', '')

        before_itp_persistant_cookies = filter_itp_persistant_cookies(before_state)
        before_urls = before_state.get('loaded_urls', [])
        exfiltrations_before = find_exfiltrated_cookies(url, before_itp_persistant_cookies, before_urls)

        after_itp_persistant_cookies = filter_itp_persistant_cookies(after_state)
        after_urls = after_state.get('loaded_urls', [])
        exfiltrations_after = find_exfiltrated_cookies(url, after_itp_persistant_cookies, after_urls)

        if len(exfiltrations_before) == 0 or len(exfiltrations_after) == 0:
            return None

        dns_lookup = build_dns_lookup(before_urls + after_urls, WORKER_TLD_EXTRACTOR)

        matching_cookies = []
        dict_before, dests_before = get_cookie_dict(exfiltrations_before)
        dict_after, dests_after = get_cookie_dict(exfiltrations_after)

        for name, values_before in dict_before.items():
            if name in dict_after:
                values_after = dict_after[name]
                static_values = values_before.intersection(values_after)
                dynamic_before = values_before - static_values
                dynamic_after = values_after - static_values

                all_destinations = set()
                if name in dests_before:
                    all_destinations.update(dests_before[name])
                if name in dests_after:
                    all_destinations.update(dests_after[name])

                id_cookie = next((c for c in before_itp_persistant_cookies if c.get('name') == name), None)
                is_http_only = id_cookie.get('httpOnly', False) if id_cookie else False
                set_by = id_cookie.get('setBy', 'unknown') if id_cookie else 'unknown'

                current_url = before_state.get('currentUrl', url)

                response = is_request_cloaked(main_dns, current_url, set_by, dns_lookup) if main_dns and set_by != 'unknown' else None
                cloaked_request, dns_record = response if response is not None else (None, None)

                expiry_longer_than_7_days = False
                if id_cookie and id_cookie.get('expires') != 'unknown':
                    try:
                        expires_timestamp = int(id_cookie.get('expires'))
                        current_timestamp = int(before_state.get('timestamp', -1).timestamp())
                        if expires_timestamp - current_timestamp > 7 * 24 * 3600:
                            expiry_longer_than_7_days = True
                    except (ValueError, TypeError):
                        pass

                if expiry_longer_than_7_days and len(dynamic_before) > 0 and len(dynamic_after) > 0:
                    matching_cookies.append({
                        "name": name,
                        "dynamic_before": list(dynamic_before),
                        "dynamic_after": list(dynamic_after),
                        "expires": id_cookie.get('expires', 'unknown') if id_cookie else 'unknown',
                        "exfiltrated_to": list(all_destinations),
                        "httpOnly": is_http_only,
                        "setBy": set_by,
                        "dnsRecord": dns_record,
                        "cloakedRequest": cloaked_request,
                    })

        if len(matching_cookies) == 0:
            return None

        return {
            "url": url,
            "crawl_time": int(before_state.get('timestamp', -1).timestamp()),
            "matching_cookies": matching_cookies,
        }
    except Exception:
        logger.error(f"Error processing {url}", exc_info=True)
        return None

def _parse_timestamp(value):
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning(f"Could not parse timestamp: {value!r}")
        return value

def _iter_filtered_records(filepath: str, fields: list[str]):
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            if "skipped" in record:
                continue
            if record.get("status") != "success":
                continue
                
            projected = {k: record[k] for k in fields if k in record}
            if "timestamp" in projected:
                projected["timestamp"] = _parse_timestamp(projected["timestamp"])
            
            yield projected

def _prewarm_tld_cache():
    extractor = tldextract.TLDExtract(cache_dir=".tld_cache", suffix_list_urls=())
    extractor("https://example.com") # warm up the cache
    return extractor

def _init_worker():
    global WORKER_TLD_EXTRACTOR
    WORKER_TLD_EXTRACTOR = tldextract.TLDExtract(cache_dir=".tld_cache", suffix_list_urls=())
    WORKER_TLD_EXTRACTOR("https://example.com") # warm up the cache
 
def _index_jsonl(filepath: str, fields: list[str]) -> dict:
    index = {}
    for record in _iter_filtered_records(filepath, fields):
        url = record.get("url")
        if url is not None:
            index[url] = record
    return index

def _process_shared_urls(
    first_index_path: str,
    second_crawl_path: str,
    fields: list[str],
    process_fn,
    max_workers: int,
    max_in_flight: int = None,
    max_tasks_per_child: int = 50,
) -> list:

    first_index = _index_jsonl(first_index_path, fields)
    logger.info(f"Indexed {len(first_index)} results from first crawl.")
    
    url_to_last_idx = {}
    for i, record in enumerate(_iter_filtered_records(second_crawl_path, ["url"])):
        url = record.get("url")
        if url in first_index:
            url_to_last_idx[url] = i
            
    last_occurrence_indices = set(url_to_last_idx.values())
    logger.info(f"Found {len(last_occurrence_indices)} intersecting final occurrences.")

    if max_in_flight is None:
        max_in_flight = max_workers  
 
    evidence = []
    matched = 0
    pending = set()
    future_url = {}  
 
    def _drain(futures_to_drain):
        for fut in futures_to_drain:
            url = future_url.pop(fut, None)
            try:
                res = fut.result()
            except Exception:
                logger.error(f"Task failed for url={url!r}", exc_info=True)
                continue
            if res:
                evidence.append(res)

    logger.info(f"Starting processing with {max_workers} workers.")
    with concurrent.futures.ProcessPoolExecutor(
             max_workers=max_workers, max_tasks_per_child=max_tasks_per_child, initializer=_init_worker,
         ) as executor:
 
        for i, record in enumerate(_iter_filtered_records(second_crawl_path, fields)):
            
            if i not in last_occurrence_indices:
                continue
                
            url = record.get("url")
            before = first_index.pop(url, None) 
            if before is None:
                continue
                
            matched += 1
 
            try:
                fut = executor.submit(process_fn, (url, before, record))
            except concurrent.futures.process.BrokenProcessPool:
                logger.error(
                    f"Pool broke while submitting url={url!r}. "
                    f"Still in flight at time of break: {list(future_url.values())}"
                )
                raise
            future_url[fut] = url
            pending.add(fut)
 
            if len(pending) >= max_in_flight:
                done, pending = concurrent.futures.wait(
                    pending, return_when=concurrent.futures.FIRST_COMPLETED
                )
                _drain(done)
                if matched % 500 == 0:
                    logger.debug(f"...{matched} matched so far, found {len(evidence)} potential circumventions.")
 
        _drain(concurrent.futures.as_completed(pending))
 
    first_index.clear()
    return evidence

async def main():
    logger.info("Starting circumvention analysis...")

    # pre-warm TLD cache
    _prewarm_tld_cache()
    
    evidence = await asyncio.to_thread(
        _process_shared_urls,
        FIRST_CRAWL_FILE,
        SECOND_CRAWL_FILE,
        PROJECTION_FIELDS,
        analyze_single_url_task,
        MAX_WORKERS,
    )
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(evidence, f, indent=4)
    logger.info(f"Analysis complete. Found {len(evidence)} URLs with potential exfiltration evidence. Results written to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    asyncio.run(main())