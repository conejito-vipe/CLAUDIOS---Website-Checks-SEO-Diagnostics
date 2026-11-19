"""Externe Links prüfen: nur über den Gatekeeper (HTTPS, gedrosselt, SSRF-Schutz), HEAD mit GET-Rückfall."""
from __future__ import annotations

import time

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

_HEAD_UNSUPPORTED = (400, 403, 405, 501)


async def _check_one(gk, url: str) -> dict:
    rec: dict = {"url": url, "status": None, "error": None, "redirects": 0}
    for method in ("HEAD", "GET"):
        try:
            resp = await gk.fetch(url, method=method, external=True, max_bytes=2048)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            rec["error"] = exc.code.value
            return rec
        rec["status"] = resp.status
        rec["error"] = E.NET_DOWNGRADE.value if resp.downgrade else None
        rec["redirects"] = len(resp.chain)
        if method == "HEAD" and resp.status in _HEAD_UNSUPPORTED:
            continue
        return rec
    return rec


async def check_external_links(gk, snap) -> dict:
    sources: dict[str, list[str]] = {}
    for pg in snap.pages:
        for link in pg.external_links:
            found = sources.setdefault(link, [])
            if len(found) < 3 and pg.url not in found:
                found.append(pg.url)
    unique = list(sources)
    started = time.monotonic()
    results: list[dict] = []
    budget_exhausted = False
    for url in unique[: LIMITS.external_links_checked]:
        if time.monotonic() - started > LIMITS.external_links_budget_seconds:
            budget_exhausted = True
            break
        rec = await _check_one(gk, url)
        rec["sources"] = sources[url]
        results.append(rec)
    return {"results": results, "unique": len(unique), "checked": len(results),
            "budget_exhausted": budget_exhausted}
