from urllib.parse import urlsplit

def escape_domain(domain: str) -> str:
    return domain.replace('https://', '').replace('http://', '').replace('.', '_').replace('-', '_').replace('/', '_').replace(':', '_')

def get_base_domain(url):
    netloc = urlsplit(url).netloc
    return netloc.replace("www.", "")