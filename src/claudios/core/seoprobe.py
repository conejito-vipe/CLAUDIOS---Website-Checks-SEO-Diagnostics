"""Sitemap- und Soft-404-Probe: wenige gezielte Anfragen, alle über den Gatekeeper (HTTPS, gedrosselt)."""
from __future__ import annotations

import html
import re
import secrets
from urllib.parse import urlsplit, urlunsplit

from publicsuffix2 import get_sld

from .crawler import norm
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

# Ohne \s* um die Gruppe: sonst ist die Suche bei vielen Leerzeichen quadratisch. Gekürzt wird in _locs().
# Auch <loc><![CDATA[...]]></loc> (manche CMS schreiben so). Leerraum nur begrenzt, [^\]]* statt .*?: beides bleibt linear.
_LOC = re.compile(r"<loc>[ \t\r\n]{0,64}(?:<!\[CDATA\[([^\]]*)\]\]>[ \t\r\n]{0,64}|([^<]*))</loc>", re.I)
# [ \t] statt \s: \s würde bei vielen Zeilenumbrüchen von jedem Zeilenanfang aus alles durchlaufen.
_SITEMAP_LINE = re.compile(r"^[ \t]*sitemap:[ \t]*(\S+)", re.I | re.M)
_HEAD_UNSUPPORTED = (400, 403, 405, 501)
_ROOT_WINDOW = 5000


def _locs(text: str) -> list[str]:
    found = (cdata.strip() or html.unescape(plain).strip() for cdata, plain in _LOC.findall(text))
    return [url for url in found if url]


def _origin(snap) -> tuple[str, str]:
    first = urlsplit(snap.pages[0].url)
    return first.scheme, first.netloc


def _text(resp) -> str:
    return resp.body.decode("utf-8", errors="replace")


def _is_sitemap(resp, root: str) -> bool:
    return resp.status == 200 and root in _text(resp)[:_ROOT_WINDOW].lower()


async def _fetch(gk, url: str, max_bytes: int):
    """Gibt None zurück, wenn die Adresse nicht abrufbar war (Abbruch und Datenlimit gehen weiter nach oben)."""
    try:
        return await gk.fetch(url, max_bytes=max_bytes)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        return None


async def _status_of(gk, url: str) -> dict:
    rec: dict = {"url": url, "status": None, "error": None, "redirects": 0}
    for method in ("HEAD", "GET"):
        try:
            resp = await gk.fetch(url, method=method, max_bytes=2048)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            rec["error"] = exc.code.value
            return rec
        rec["status"] = resp.status
        rec["redirects"] = len(resp.chain)
        if method == "HEAD" and resp.status in _HEAD_UNSUPPORTED:
            continue
        return rec
    return rec


async def collect_sitemap(gk, snap) -> dict:
    scheme, netloc = _origin(snap)
    default = urlunsplit((scheme, netloc, "/sitemap.xml", "", ""))
    declared = [m.group(1) for m in _SITEMAP_LINE.finditer(snap.robots_txt or "")][:3]
    candidates = declared + ([default] if default not in declared else [])
    data: dict = {"found": False, "declared": bool(declared), "reachable": False, "source": None,
                  "index": False, "child_failed": False, "urls": [], "total": 0, "truncated": False,
                  "checked": []}
    body = None
    for url in candidates:
        resp = await _fetch(gk, url, LIMITS.sitemap_bytes_max)
        if resp is None:
            continue
        data["reachable"] = True
        low = _text(resp)[:_ROOT_WINDOW].lower()
        if resp.status == 200 and ("<urlset" in low or "<sitemapindex" in low):
            body, data["source"], data["index"] = _text(resp), url, "<sitemapindex" in low
            break
    if body is None:
        return data
    data["found"] = True
    if data["index"]:
        children = _locs(body)
        body = None
        if children:
            resp = await _fetch(gk, children[0], LIMITS.sitemap_bytes_max)
            if resp is not None and _is_sitemap(resp, "<urlset"):
                body = _text(resp)
        if body is None:
            data["child_failed"] = True
            return data
    locs = _locs(body)
    data["total"] = len(locs)
    data["truncated"] = len(locs) > LIMITS.sitemap_urls_stored
    data["urls"] = locs[: LIMITS.sitemap_urls_stored]

    crawled: set[str] = set()
    for pg in snap.pages:
        crawled.add(norm(pg.url))
        crawled.update(norm(u) for u in pg.chain)
    todo: list[str] = []
    for url in data["urls"]:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or (get_sld(host) or "") != snap.target.registrable:
            continue
        if norm(url) in crawled:
            continue
        todo.append(url)
        if len(todo) >= LIMITS.sitemap_urls_checked:
            break
    for url in todo:
        data["checked"].append(await _status_of(gk, url))
    return data


async def probe_soft404(gk, snap) -> dict:
    """Genau eine Anfrage an eine zufällige, nicht existierende Adresse."""
    scheme, netloc = _origin(snap)
    url = urlunsplit((scheme, netloc, f"/claudios-check-{secrets.token_hex(6)}", "", ""))
    rec: dict = {"status": None, "error": None, "redirects": 0, "final": None}
    resp = None
    try:
        resp = await gk.fetch(url, max_bytes=100_000)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        rec["error"] = exc.code.value
    if resp is not None:
        rec["status"] = resp.status
        rec["redirects"] = len(resp.chain)
        rec["final"] = resp.url
    return rec
