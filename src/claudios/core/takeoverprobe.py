"""Takeover-Hinweise: nur DNS-Abfragen (DoH) für Subdomains, die auf der Seite vorkommen. Kein Brute-Force."""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from .limits import LIMITS

SERVICES = (
    ("github.io", "GitHub Pages"), ("herokuapp.com", "Heroku"), ("herokudns.com", "Heroku"),
    ("azurewebsites.net", "Azure App Service"), ("cloudapp.net", "Azure"),
    ("cloudapp.azure.com", "Azure"), ("trafficmanager.net", "Azure Traffic Manager"),
    ("blob.core.windows.net", "Azure Blob Storage"), ("azureedge.net", "Azure CDN"),
    ("elasticbeanstalk.com", "AWS Elastic Beanstalk"), ("s3.amazonaws.com", "AWS S3"),
    ("cloudfront.net", "AWS CloudFront"), ("netlify.app", "Netlify"), ("vercel.app", "Vercel"),
    ("pages.dev", "Cloudflare Pages"), ("myshopify.com", "Shopify"), ("ghost.io", "Ghost"),
    ("surge.sh", "Surge"), ("bitbucket.io", "Bitbucket"), ("zendesk.com", "Zendesk"),
    ("statuspage.io", "Statuspage"), ("readme.io", "Readme"), ("helpscoutdocs.com", "Help Scout"),
    ("fastly.net", "Fastly"),
)
_RESOURCE_TAGS = (("script", "src"), ("img", "src"), ("link", "href"), ("iframe", "src"), ("source", "src"))


def service_for(target: str) -> str | None:
    host = target.rstrip(".").lower()
    for suffix, name in SERVICES:
        if host == suffix or host.endswith("." + suffix):
            return name
    if host.endswith(".amazonaws.com") and (".s3" in host or "s3-website" in host or host.startswith("s3")):
        return "AWS S3"
    return None


def candidate_hosts(snap) -> list[str]:
    registrable = snap.target.registrable
    hosts: set[str] = set()

    def consider(url: str) -> None:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        if host and host != snap.target.host and host.endswith("." + registrable):
            hosts.add(host)

    for pg in snap.pages:
        for link in pg.external_links + pg.insecure_links:
            consider(link)
        if pg.html is None:
            continue
        for tag, attr in _RESOURCE_TAGS:
            for element in pg.soup.find_all(tag):
                value = str(element.get(attr, "")).strip()
                if value:
                    consider(urljoin(pg.url, value))
    return sorted(hosts)[: LIMITS.takeover_hosts_max]


async def _query(resolver, state: dict, name: str, rtype: str):
    """None = unbekannt (Fehler oder Abfragelimit), [] = der Eintrag existiert nicht."""
    if state["n"] >= LIMITS.takeover_queries_max:
        state["limited"] = True
        return None
    state["n"] += 1
    try:
        return await resolver.query(name, rtype)
    except Exception:  # noqa: BLE001 – ein DNS-Fehler bedeutet nur: unbekannt
        return None


async def _inspect(resolver, state: dict, host: str) -> dict | None:
    chain: list[str] = []
    current = host
    for _ in range(4):
        answer = await _query(resolver, state, current, "CNAME")
        if not answer:
            break
        current = answer[0].rstrip(".").lower()
        chain.append(current)
    if not chain:
        return None
    a = await _query(resolver, state, current, "A")
    aaaa = await _query(resolver, state, current, "AAAA")
    if any(x for x in (a, aaaa) if x):
        resolves: bool | None = True
    elif a == [] and aaaa == []:
        resolves = False
    else:
        resolves = None
    return {"host": host, "chain": chain, "target": current, "service": service_for(current),
            "resolves": resolves}


async def collect_takeover(resolver, snap) -> dict:
    hosts = candidate_hosts(snap)
    state = {"n": 0, "limited": False}
    records = []
    for host in hosts:
        rec = await _inspect(resolver, state, host)
        if rec is not None:
            records.append(rec)
    return {"hosts": len(hosts), "records": records, "queries": state["n"], "limited": state["limited"]}
