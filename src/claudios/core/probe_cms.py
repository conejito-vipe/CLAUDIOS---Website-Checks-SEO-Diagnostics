"""CMS-Zusatzpfade (aktive Prüfung, nur Stufe 2): Nur wenn ein CMS erkannt wurde (WordPress, Joomla), je zwei feste Pfade
per GET über den Gatekeeper (HTTPS, gedrosselt, keine Weiterleitungen, keine Payloads, kein Raten, keine Anmeldung).
Inhalte werden nie gespeichert, nur Pfad, Art und Treffer. Ausgewertet wird in checks/quality_extra.py."""
from __future__ import annotations

from .errors import ClaudiosError, ErrorCode as E

NAME = "cms"
MIN_LEVEL = 2


def detect_cms(html: str) -> str | None:
    low = (html or "").lower()
    if "wp-content/" in low or 'content="wordpress' in low:
        return "wordpress"
    if 'content="joomla' in low or "/media/system/js/" in low:
        return "joomla"
    return None


CMS_PATHS = {
    "wordpress": (("xmlrpc.php", "xmlrpc", ("xml-rpc server accepts post requests only",), (200, 405)),
                  ("wp-json/wp/v2/users", "users", ('"slug"',), (200,))),
    "joomla": (("administrator/", "admin", ("joomla",), (200,)),
               ("administrator/manifests/files/joomla.xml", "version", ("<version>",), (200,))),
}


async def collect(gk, snap, resolver) -> dict | None:
    first = snap.docs()[0] if snap.docs() else None
    cms = detect_cms(first.html) if first is not None else None
    if cms is None:
        return None
    out = {"cms": cms, "hits": [], "errors": 0, "total": len(CMS_PATHS[cms])}
    for path, kind, signs, statuses in CMS_PATHS[cms]:
        try:
            resp = await gk.fetch(f"https://{snap.target.host}/{path}", follow=False, max_bytes=4096)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            out["errors"] += 1
            continue
        text = resp.body.decode("utf-8", "replace").lower()
        if resp.status in statuses and any(s in text for s in signs):
            out["hits"].append({"path": path, "kind": kind})
    return out



