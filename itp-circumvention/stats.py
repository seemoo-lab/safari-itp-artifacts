import logging
import asyncio
import collections
import json
import tldextract
import os
from typing import List, Dict, Any

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CircumventionStats")


RESULTS_DIR = "results"
INPUT_PATH = "exfiltration_blocklist_matches.json"
OUTPUT_PATH = os.path.join(RESULTS_DIR, "successful_circumventions.json")

TOP_COOKIE_NAMES = os.path.join(RESULTS_DIR, "top_cookies_lifetime_table.md")
TOP_EXFILTRATED_DOMAINS = os.path.join(RESULTS_DIR, "top_exfiltrated_domains_table.md")
TOP_N = 10

GOOGLE_DOMAINS = [
    'google.com', 'google.de', 'google-analytics.com', 'doubleclick.net', 
    'gstatic.com', 'googlesyndication.com', 'googleusercontent.com', 
    'googleapis.com', 'googletagmanager.com', 'googleservices.com', 
    'googleadservices.com'
]


def read_data(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def cleanup(data):
    for site in data:
        site['matching_cookies'] = [cookie for cookie in site['matching_cookies'] if cookie.get('cloakedRequest') is not None]
    return data

def top_cookie_names(cookie_name_counts, filtered_data, top_n=10):
    total_cookies = sum(cookie_name_counts.values())
    top_cookies = cookie_name_counts.most_common(top_n)
    top_cookie_names = set(name for name, _ in top_cookies)

    cookie_lifetimes = {}

    for site in filtered_data:
        for cookie in site.get('matching_cookies', []):
            name = cookie.get('name')
            
            if name in top_cookie_names and name not in cookie_lifetimes:
                expires = cookie.get('expires')
                crawl_time = site.get('crawl_time')
                
                if expires and crawl_time and expires != 'unknown':
                    try:
                        lifetime = round((float(expires) - float(crawl_time)) / (60 * 60 * 24))
                        cookie_lifetimes[name] = lifetime
                    except (ValueError, TypeError):
                        cookie_lifetimes[name] = "Unknown"
                else:
                    cookie_lifetimes[name] = "Session/Unknown"

    top_n_total = sum(count for _, count in top_cookies)
    coverage_percentage = (top_n_total / total_cookies) * 100 if total_cookies > 0 else 0

    lines = [
        "| Cookie Name | Lifetime | Count (%) |",
        "|---|---|---|"
    ]
    
    for name, count in top_cookies:
        percentage = (count / total_cookies) * 100 if total_cookies > 0 else 0
        lifetime = cookie_lifetimes.get(name, "Unknown")
        
        lines.append(f"| {name} | {lifetime} d | {count} ({percentage:.2f}%) |")

    logger.info(f"Cookies covered by top {len(top_cookies)} cookies: {top_n_total} ({coverage_percentage:.2f}%)")
        
    return "\n".join(lines)

def top_exfiltrated_domains(filtered_data, top_n=10):
    exfiltrated_to_counts = collections.Counter()
    
    for site in filtered_data:
        for cookie in site.get('matching_cookies', []):
            for url in cookie.get('exfiltrated_to', []):

                domain = tldextract.extract(url).top_domain_under_public_suffix
                if domain:
                    exfiltrated_to_counts[domain] += 1

    total_exfiltrations = sum(exfiltrated_to_counts.values())
    top_domains = exfiltrated_to_counts.most_common(top_n)

    top_n_total = sum(count for _, count in top_domains)
    coverage_percentage = (top_n_total / total_exfiltrations) * 100 if total_exfiltrations > 0 else 0

    google_exfiltrations_count = sum(count for domain, count in exfiltrated_to_counts.items() if domain in GOOGLE_DOMAINS)
    google_percentage = (google_exfiltrations_count / total_exfiltrations) * 100 if total_exfiltrations > 0 else 0

    lines = [
        "| Domain | Count (%) |",
        "|---|---|"
    ]
    
    for domain, count in top_domains:
        percentage = (count / total_exfiltrations) * 100 if total_exfiltrations > 0 else 0
        lines.append(f"| {domain} | {count} ({percentage:.2f}%) |")

    logger.info(f"Exfiltrations covered by top {len(top_domains)} exfiltration domains: {top_n_total} ({coverage_percentage:.2f}%)")
    logger.info(f"Exfiltrations to Google-owned domains: {google_exfiltrations_count} ({google_percentage:.2f}%)")
        
    return "\n".join(lines)

async def main():
    logger.info(f"Starting circumvention statistics analysis, reading {INPUT_PATH}")
    data = read_data(INPUT_PATH)
    data = cleanup(data)

    # filter out all cookies that have cloakedRequest null
    for site in data:
        site['matching_cookies'] = [cookie for cookie in site['matching_cookies'] if cookie.get('cloakedRequest') is not None]

    # filter out websites that have no matching cookies after filtering
    data = [site for site in data if site['matching_cookies']]

    total_cookies = sum(len(site['matching_cookies']) for site in data)
    logger.info(f"Total websites exfiltrating cookies: {len(data)}")
    logger.info(f"Total cookies exfiltrated: {total_cookies}")

    # Use sets to easily find intersections and overlaps
    sites_with_cname = set()
    sites_with_ip = set()
    sites_with_both = set()

    # Counters for tracking individual cookies
    cname_cookies_count = 0
    ip_cookies_count = 0
    cname_ip_overlap_cookies = 0

    filtered_data = []

    for site in data:
        url_domain = tldextract.extract(site['url']).top_domain_under_public_suffix
        
        valid_cookies = []
        
        for cookie in site['matching_cookies']:
            is_cname_mismatch = False
            is_ip_cloaked = False
            
            # Check CNAME Mismatch
            if cookie.get('dnsRecord') and cookie['dnsRecord'].get('CNAME'):
                for cname in cookie['dnsRecord']['CNAME']:
                    cname_domain = tldextract.extract(cname).top_domain_under_public_suffix
                    if url_domain != cname_domain:
                        is_cname_mismatch = True
                        break
                        
            # Check IP Cloaking
            if cookie.get('cloakedRequest'):
                is_ip_cloaked = True
                
            # Update site sets and cookie counters based on findings
            if is_cname_mismatch:
                sites_with_cname.add(site['url'])
                cname_cookies_count += 1
                
            if is_ip_cloaked:
                sites_with_ip.add(site['url'])
                ip_cookies_count += 1

            # Check overlap
            if is_cname_mismatch and is_ip_cloaked:
                sites_with_both.add(site['url'])
                cname_ip_overlap_cookies += 1

            # Keep only cookies if both do not match
            if not is_cname_mismatch and not is_ip_cloaked:
                valid_cookies.append(cookie)
                
        # If the site still has at least one valid cookie, keep the site in the final dataset
        if valid_cookies:
            filtered_data.append({
                'url': site['url'],
                'crawl_time': site.get('crawl_time'),
                'matching_cookies': valid_cookies
            })

    # Output detailed logging for COOKIES
    logger.info(f"Cookies set via CNAME mismatch: {cname_cookies_count}")
    logger.info(f"Cookies set via IP cloaking: {ip_cookies_count}")
    logger.info(f"Cookies with BOTH CNAME mismatch and IP cloaking: {cname_ip_overlap_cookies}")

    total_cookies_after_filtering = sum(len(site['matching_cookies']) for site in filtered_data)
    logger.info(f"Total websites evading ITP script-written purge: {len(filtered_data)}")
    logger.info(f"Total cookies evading ITP script-written purge: {total_cookies_after_filtering}")

    # print result to json file for filtered_data
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(filtered_data, f, indent=4)
    logger.info(f"Results written to {OUTPUT_PATH}")

    # calculate average cookie lifetime in days (expires - creation) for cookies with expires and creation
    lifetimes = []
    for site in filtered_data:
        for cookie in site['matching_cookies']:
            if cookie['expires'] and site['crawl_time']:
                lifetime = (cookie['expires'] - site['crawl_time'])
                lifetimes.append(lifetime)
    mean_lifetime = sum(lifetimes) / len(lifetimes)
    logger.info(f"Average cookie lifetime (in days): {round(mean_lifetime / (60 * 60 * 24))}")

    # top cookie names
    cookie_name_counts = collections.Counter()
    for site in filtered_data:
        for cookie in site['matching_cookies']:
            cookie_name_counts[cookie['name']] += 1

    # top 10 cookie names account for what % of total cookies
    top_10_accounts_for = sum(count for _, count in cookie_name_counts.most_common(10))
    logger.info(f"Top 10 cookie names account for {top_10_accounts_for} out of {total_cookies_after_filtering} cookies ({(top_10_accounts_for / total_cookies_after_filtering) * 100:.2f}%)")

    # Table 4: Top 10 most frequent persistent cookies
    markdown_table = top_cookie_names(cookie_name_counts, filtered_data, top_n=TOP_N)
    with open(TOP_COOKIE_NAMES, 'w') as f:
        f.write(markdown_table)
    logger.info(f"Top {TOP_N} most frequent persistent cookies table written to {TOP_COOKIE_NAMES}")

    # Table 5: Top 10 domains receiving persistent tracking identifiers
    markdown_table = top_exfiltrated_domains(filtered_data, top_n=TOP_N)
    with open(TOP_EXFILTRATED_DOMAINS, 'w') as f:
        f.write(markdown_table)
    logger.info(f"Top {TOP_N} domains receiving persistent tracking identifiers table written to {TOP_EXFILTRATED_DOMAINS}")


if __name__ == "__main__":
    asyncio.run(main())
