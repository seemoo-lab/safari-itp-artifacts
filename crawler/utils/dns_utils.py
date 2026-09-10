import dns.resolver

RESOLVER = "1.1.1.1"

def resolve_domain_rr(domain: str, record_type: str = 'A', resolver: str = RESOLVER) -> list:
    try:
        answers = dns.resolver.resolve_at(resolver, domain, record_type)
        return list(set([str(rdata) for rdata in answers]))
    except Exception as e:
        return []
