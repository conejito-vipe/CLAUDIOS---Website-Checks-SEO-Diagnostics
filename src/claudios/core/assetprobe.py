"""Skripte und Stile der eigenen Domain holen (wenige, über den Gatekeeper). Die Texte bleiben im Snapshot
und werden nie exportiert; nur die Befunde der Prüfungen landen im Bericht."""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from publicsuffix2 import get_sld

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS


def _same_site(snap, url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    return host == snap.target.host or (get_sld(host) or host) == snap.target.registrable


def _collect_urls(snap) -> tuple[list[str], list[str]]:
    css: list[str] = []
    js: list[str] = []
    for pg in snap.docs():
        for tag in pg.soup.find_all("link", href=True):
            rels = {r.lower() for r in (tag.get("rel") or [])}
            url = urljoin(pg.url, str(tag["href"]).strip()).split("#")[0]
            if "stylesheet" in rels and url not in css and _same_site(snap, url):
                css.append(url)
        for tag in pg.soup.find_all("script", src=True):
            url = urljoin(pg.url, str(tag["src"]).strip()).split("#")[0]
            if url not in js and _same_site(snap, url):
                js.append(url)
    return css, js


async def _fetch_all(gk, urls: list[str], limit: int) -> list[dict]:
    out = []
    for url in urls[:limit]:
        rec: dict = {"url": url, "status": None, "error": None, "text": "", "truncated": False}
        try:
            resp = await gk.fetch(url, max_bytes=LIMITS.assets_bytes_max)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            rec["error"] = exc.code.value
            out.append(rec)
            continue
        rec["status"] = resp.status
        rec["truncated"] = resp.truncated
        if resp.status == 200:
            rec["text"] = resp.body.decode("utf-8", errors="replace")
        out.append(rec)
    return out


async def collect_assets(gk, snap) -> dict:
    css_urls, js_urls = _collect_urls(snap)
    return {
        "css": await _fetch_all(gk, css_urls, LIMITS.assets_css_max),
        "js": await _fetch_all(gk, js_urls, LIMITS.assets_js_max),
        "css_total": len(css_urls),
        "js_total": len(js_urls),
    }