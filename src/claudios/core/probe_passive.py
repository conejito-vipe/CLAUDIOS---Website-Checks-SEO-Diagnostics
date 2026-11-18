"""Zusatzdateien nach dem Crawl: security.txt, Favicon, MTA-STS-Richtlinie und Fehlerseiten von Subdomains, die auf
Fremddienste zeigen. Alles über den Gatekeeper (HTTPS, gedrosselt, nur GET), insgesamt etwa zehn Anfragen.
Die Daten landen in snap.extra["passive"]; ausgewertet wird in checks/headers_more.py, checks/seo_extra.py und
checks/infra_more.py. Die Fehlertexte der Dienste stammen aus der öffentlichen Liste can-i-take-over-xyz; die
Praxisprüfung auf GitHub hat alle acht Dienste bestätigt (Ghost wurde korrigiert). Dienste ändern ihre Texte, deshalb
ist der Befund eine Warnung und kein Fehler."""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from publicsuffix2 import get_sld

from .dnsprobe import txt_join
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "passive"
MIN_LEVEL = 1

# Dienst (wie in takeoverprobe.SERVICES) -> typische Fehlertexte einer freien Ressource, kleingeschrieben.
FINGERPRINTS = {
    "GitHub Pages": ("there isn't a github pages site here",),
    "Heroku": ("no such app",),
    "AWS S3": ("nosuchbucket", "the specified bucket does not exist"),
    "Shopify": ("sorry, this shop is currently unavailable",),
    "Surge": ("project not found",),
    "Bitbucket": ("repository not found",),
    "Ghost": ("site unavailable.", "failed to resolve dns path for this host"),
    "Fastly": ("fastly error: unknown domain",),
}


async def _get(gk, url: str, path: str, *, follow: bool = True, any_status: bool = False) -> dict:
    rec: dict = {"path": path, "status": None, "error": None, "content_type": "", "text": ""}
    try:
        resp = await gk.fetch(url, follow=follow, max_bytes=LIMITS.passive_body_max)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        rec["error"] = exc.code.value
        return rec
    rec["status"] = resp.status
    rec["content_type"] = (resp.header("content-type") or "").lower()
    if resp.status == 200 or any_status:
        rec["text"] = resp.body.decode("utf-8", errors="replace")[: LIMITS.passive_body_max]
    return rec


async def _security_txt(gk, origin: str) -> dict:
    rec = await _get(gk, origin + "/.well-known/security.txt", "/.well-known/security.txt")
    rec["legacy"] = None
    if rec["status"] in (404, 410):
        rec["legacy"] = await _get(gk, origin + "/security.txt", "/security.txt")
    return rec


def _icon_link(page) -> str:
    soup = page.soup
    if soup is None:
        return ""
    fallback = ""
    for link in soup.find_all("link", href=True):
        rels = [str(r).lower() for r in link.get("rel") or []]
        if "icon" in rels:
            return str(link["href"]).strip()
        if not fallback and any(r.startswith("apple-touch-icon") for r in rels):
            fallback = str(link["href"]).strip()
    return fallback


async def _favicon(gk, snap, origin: str) -> dict:
    docs = snap.docs()
    if not docs:
        return {"skipped": True}
    start = docs[0]
    href = _icon_link(start)
    data: dict = {"skipped": False, "declared": bool(href), "inline": False, "external": False, "fetch": None}
    if not href:
        data["fetch"] = await _get(gk, origin + "/favicon.ico", "/favicon.ico")
        return data
    if href.lower().startswith("data:"):
        data["inline"] = True
        return data
    url = urljoin(start.url, href).split("#")[0]
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or (get_sld(host) or host) != snap.target.registrable:
        data["external"] = True  # fremde oder unverschlüsselte Adresse: wird nicht abgerufen
        return data
    data["fetch"] = await _get(gk, url, parts.path or "/")
    return data


async def _mta_sts(gk, snap) -> dict | None:
    dns = snap.extra.get("dns")
    records = dns.get("records") if isinstance(dns, dict) else None
    if not isinstance(records, dict):
        return None
    texts = [txt_join(x).lower() for x in records.get("mta_sts") or []]
    if not any(text.startswith("v=stsv1") for text in texts):
        return None
    host = f"mta-sts.{snap.target.registrable}"
    # Die Richtlinie darf laut Spezifikation nicht weitergeleitet werden.
    return await _get(gk, f"https://{host}/.well-known/mta-sts.txt", "/.well-known/mta-sts.txt", follow=False)


async def _takeover(gk, snap) -> list[dict] | None:
    data = snap.extra.get("takeover")
    if not isinstance(data, dict):
        return None
    out: list[dict] = []
    for rec in data.get("records") or []:
        if len(out) >= LIMITS.passive_takeover_hosts:
            break
        service = rec.get("service")
        signs = FINGERPRINTS.get(service or "")
        if not signs or rec.get("resolves") is not True:
            continue
        host = str(rec.get("host", ""))
        fetched = await _get(gk, f"https://{host}/", "/", any_status=True)
        body = fetched["text"].lower()
        out.append({"host": host, "service": service, "status": fetched["status"], "error": fetched["error"],
                    "matched": any(sign in body for sign in signs)})
    return out


async def collect(gk, snap, resolver) -> dict:
    first = urlsplit(snap.pages[0].url)
    origin = f"{first.scheme}://{first.netloc}"
    return {
        "security_txt": await _security_txt(gk, origin),
        "favicon": await _favicon(gk, snap, origin),
        "mta_sts": await _mta_sts(gk, snap),
        "takeover": await _takeover(gk, snap),
    }
