"""Zusatzanfragen für weitere Prüfungen, alle über den Gatekeeper (gedrosselt, öffentliche IP, nur GET oder HEAD):
1. Adress-Varianten: http und www/ohne www, je EINE Anfrage ohne Weiterleitung (nur die eigene Domain).
2. Bilder: HEAD auf wenige Bilder (Typ und Größe).
3. Statische Dateien: HEAD auf die bereits geladenen CSS- und JS-Adressen (Cache- und Kompressions-Header).
4. Global Privacy Control: /.well-known/gpc.json und die Startseite mit dem Signal Sec-GPC (Vergleich der Fremdserver).
5. Ablauf der Domains eingebundener Fremdskripte (nur wenn der Schalter 'rdap' an ist, wie beim Domainablauf).
Die Daten landen in snap.extra["extra"]; ausgewertet wird in checks/quality_extra.py. Inhalte werden nicht gespeichert."""
from __future__ import annotations

import re
from urllib.parse import quote, urljoin, urlsplit

from publicsuffix2 import get_sld

from . import probe_rdap, services
from .errors import ClaudiosError, ErrorCode as E

NAME = "extra"
MIN_LEVEL = 1
MAX_IMAGES = 8
MAX_ASSETS = 6
MAX_FOREIGN = 5
_PLAIN = "http" + ":" + "//"
_SRC_TAGS = (("script", "src"), ("img", "src"), ("iframe", "src"), ("link", "href"))


def alt_host(host: str, registrable: str) -> str | None:
    """Die andere Schreibweise: www.example.com <-> example.com. Für Unterdomains gibt es keine."""
    if host.startswith("www.") and host[4:] == registrable:
        return registrable
    return "www." + host if host == registrable else None


def external_hosts(html: str, base: str, own_host: str, registrable: str) -> list[str]:
    """Hosts fremder Domains, die die Seite einbindet (Skripte, Bilder, Frames, Stile), sortiert und ohne Doppelte."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    found: set[str] = set()
    for tag, attr in _SRC_TAGS:
        for el in soup.find_all(tag, attrs={attr: True}):
            if tag == "link" and "stylesheet" not in [str(r).lower() for r in el.get("rel") or []]:
                continue
            host = (urlsplit(urljoin(base, str(el[attr]).strip())).hostname or "").lower()
            if host and host != own_host and (get_sld(host) or host) != registrable:
                found.add(host)
    return sorted(found)


async def _try(gk, url: str, **kw):
    """Antwort oder Fehlercode (str). Abbruch und Datenlimit gehen weiter nach oben."""
    try:
        return await gk.fetch(url, **kw)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        return exc.code.value


async def _variants(gk, snap) -> dict:
    host, reg = snap.target.host, snap.target.registrable
    other = alt_host(host, reg)
    plan = [("http", f"{_PLAIN}{host}/", True), ("https_alt", f"https://{other}/", False) if other else None,
            ("http_alt", f"{_PLAIN}{other}/", True) if other else None]
    out: dict = {"host": host, "alt": other, "items": {}}
    for item in filter(None, plan):
        name, url, plain = item
        resp = await _try(gk, url, follow=False, max_bytes=2048, plain=plain)
        if isinstance(resp, str):
            out["items"][name] = {"error": resp}
        else:
            out["items"][name] = {"status": resp.status, "location": (resp.header("location") or "")[:300]}
    return out


async def _images(gk, snap) -> list[dict]:
    seen: list[str] = []
    for pg in snap.docs():
        for img in pg.soup.find_all("img", src=True):
            url = urljoin(pg.url, str(img["src"]).strip()).split("#")[0]
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
            if (parts.scheme == "https" and url not in seen and not url.startswith("data:")
                    and (host == snap.target.host or (get_sld(host) or host) == snap.target.registrable)):
                seen.append(url)
    out = []
    for url in seen[:MAX_IMAGES]:
        resp = await _try(gk, url, method="HEAD", max_bytes=1024)
        if isinstance(resp, str):
            out.append({"url": url, "error": resp})
            continue
        length = resp.header("content-length")
        out.append({"url": url, "status": resp.status, "type": (resp.header("content-type") or "").lower(),
                    "length": int(length) if length and length.isdigit() else None})
    return out


async def _assets(gk, snap) -> list[dict]:
    data = snap.extra.get("assets")
    if not isinstance(data, dict):
        return []
    urls = [(kind, rec["url"]) for kind in ("css", "js") for rec in (data.get(kind) or [])[:MAX_ASSETS]
            if rec.get("status") == 200]
    out = []
    for kind, url in urls:
        resp = await _try(gk, url, method="HEAD", max_bytes=1024)
        if isinstance(resp, str):
            continue
        length = resp.header("content-length")
        out.append({"url": url, "kind": kind, "status": resp.status, "cache": (resp.header("cache-control") or "").lower(),
                    "expires": bool(resp.header("expires")), "etag": bool(resp.header("etag")),
                    "encoding": (resp.header("content-encoding") or "").lower(),
                    "length": int(length) if length and length.isdigit() else None})
    return out


async def _gpc(gk, snap) -> dict:
    origin = f"https://{snap.target.host}"
    wk = await _try(gk, origin + "/.well-known/gpc.json", max_bytes=2048, follow=False)
    declared = None
    if not isinstance(wk, str) and wk.status == 200:
        declared = bool(re.search(r'"gpc"\s*:\s*true', wk.body.decode("utf-8", "replace")))
    first = snap.docs()[0] if snap.docs() else None
    hosts = None
    if first is not None:
        resp = await _try(gk, first.url, headers={"Sec-GPC": "1"}, max_bytes=500_000)
        if not isinstance(resp, str) and resp.status == 200:
            html = resp.body.decode("utf-8", "replace")
            hosts = external_hosts(html, first.url, snap.target.host, snap.target.registrable)
    return {"declared": declared, "hosts_with_signal": hosts}


async def _foreign_domains(gk, snap) -> dict | None:
    if not services.enabled("rdap"):
        return None
    domains: list[str] = []
    for pg in snap.docs():
        for host in external_hosts(pg.html, pg.url, snap.target.host, snap.target.registrable):
            dom = get_sld(host) or host
            if dom not in domains and dom != snap.target.registrable:
                domains.append(dom)
    scripts = []
    for pg in snap.docs():
        for el in pg.soup.find_all("script", src=True):
            host = (urlsplit(urljoin(pg.url, str(el["src"]).strip())).hostname or "").lower()
            dom = get_sld(host) or host
            if host and dom in domains and dom not in scripts:
                scripts.append(dom)
    if not scripts:
        return {"checked": [], "skip": None}
    boot, reason = await probe_rdap._get_json(gk, probe_rdap.BOOTSTRAP)
    if boot is None:
        return {"checked": [], "skip": reason}
    checked = []
    for dom in scripts[:MAX_FOREIGN]:
        server = probe_rdap.server_for(boot, dom.rsplit(".", 1)[-1].lower())
        if server is None:
            continue
        data, why = await probe_rdap._get_json(gk, f"{server}domain/{quote(dom, safe='')}")
        checked.append({"domain": dom, **(probe_rdap.parse_domain(data) if isinstance(data, dict)
                                          else {"expires": None, "statuses": [], "error": why})})
    return {"checked": checked, "skip": None}


async def collect(gk, snap, resolver) -> dict:
    if not snap.docs():
        return {"skipped": True}
    return {
        "skipped": False,
        "variants": await _variants(gk, snap),
        "images": await _images(gk, snap),
        "assets": await _assets(gk, snap),
        "gpc": await _gpc(gk, snap),
        "foreign_domains": await _foreign_domains(gk, snap),
    }
