"""llms.txt: genau eine Anfrage über den Gatekeeper (HTTPS, gedrosselt, nur GET, nur die geprüfte Website).
Ausgewertet wird in checks/ai_visibility.py."""
from __future__ import annotations

from urllib.parse import urlsplit

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "ai"
MIN_LEVEL = 1


async def collect(gk, snap, resolver) -> dict:
    first = urlsplit(snap.pages[0].url)
    rec: dict = {"path": "/llms.txt", "status": None, "error": None, "content_type": "", "text": "",
                 "truncated": False}
    try:
        resp = await gk.fetch(f"{first.scheme}://{first.netloc}/llms.txt", max_bytes=LIMITS.llms_body_max)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        rec["error"] = exc.code.value
        return {"llms": rec}
    rec["status"] = resp.status
    rec["content_type"] = (resp.header("content-type") or "").lower()
    rec["truncated"] = bool(resp.truncated)
    if resp.status == 200:
        rec["text"] = resp.body.decode("utf-8", errors="replace")[: LIMITS.llms_body_max]
    return {"llms": rec}
