"""ads.txt und app-ads.txt: nur abrufen, wenn Werbung erkannt wurde (höchstens 2 Anfragen über den Gatekeeper)."""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

AD_HOSTS = ("googlesyndication.com", "doubleclick.net", "googleadservices.com", "adnxs.com",
            "amazon-adsystem.com", "criteo.com", "taboola.com", "outbrain.com", "pubmatic.com",
            "rubiconproject.com", "openx.net")


def detect_ads(snap) -> list[str]:
    found: set[str] = set()
    for pg in snap.docs():
        soup = pg.soup
        for tag in soup.find_all("script", src=True):
            src = str(tag["src"]).lower()
            found.update(host for host in AD_HOSTS if host in src)
        if soup.find("ins", class_="adsbygoogle") is not None:
            found.add("adsbygoogle")
    return sorted(found)


async def _get(gk, url: str, path: str) -> dict:
    rec: dict = {"path": path, "status": None, "error": None, "content_type": "", "text": ""}
    try:
        resp = await gk.fetch(url, max_bytes=LIMITS.ads_bytes_max)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        rec["error"] = exc.code.value
        return rec
    rec["status"] = resp.status
    rec["content_type"] = (resp.header("content-type") or "").lower()
    if resp.status == 200:
        rec["text"] = resp.body.decode("utf-8", errors="replace")
    return rec


async def fetch_ads(gk, snap) -> dict:
    detected = detect_ads(snap)
    data: dict = {"detected": detected, "files": []}
    if not detected:
        return data
    first = urlsplit(snap.pages[0].url)
    for path in ("/ads.txt", "/app-ads.txt"):
        url = urlunsplit((first.scheme, first.netloc, path, "", ""))
        data["files"].append(await _get(gk, url, path))
    return data
