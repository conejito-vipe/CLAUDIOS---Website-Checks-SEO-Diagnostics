"""Externe Links prüfen: nur über den Gatekeeper (HTTPS, gedrosselt, SSRF-Schutz), HEAD mit GET-Rückfall.
Es werden keine Seiten gelesen und keinen Weiterleitungen gefolgt: nur der Statuscode zählt (follow=False). Jeder Link hat ein
festes Zeitlimit; antwortet ein Host zweimal nicht, werden seine übrigen Links nicht mehr versucht (sonst hält ein toter
Server den ganzen Scan auf). Fortschritt und Abbruch werden je Link geprüft."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

_HEAD_UNSUPPORTED = (400, 403, 405, 501)
_REDIRECTS = (301, 302, 303, 307, 308)
LINK_TIMEOUT = 8.0      # Sekunden je Link (HEAD und GET zusammen)
SLOW_HOST_LIMIT = 2     # so viele Zeitüberschreitungen je Host, danach werden seine übrigen Links übersprungen


async def _check_one(gk, url: str) -> dict:
    rec: dict = {"url": url, "status": None, "error": None, "redirects": 0}
    for method in ("HEAD", "GET"):
        try:
            resp = await gk.fetch(url, method=method, follow=False, external=True, max_bytes=2048)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            rec["error"] = exc.code.value
            return rec
        rec["status"] = resp.status
        rec["error"] = E.NET_DOWNGRADE.value if resp.downgrade else None
        rec["redirects"] = 1 if resp.status in _REDIRECTS else 0
        if method == "HEAD" and resp.status in _HEAD_UNSUPPORTED:
            continue
        return rec
    return rec


def _timeout_record(url: str) -> dict:
    return {"url": url, "status": None, "error": E.NET_TIMEOUT.value, "redirects": 0}


async def _check_guarded(gk, url: str) -> dict:
    try:
        return await asyncio.wait_for(_check_one(gk, url), LINK_TIMEOUT)
    except TimeoutError:
        return _timeout_record(url)


async def check_external_links(gk, snap, progress: Callable[[str, int, int], None] | None = None) -> dict:
    report = progress or (lambda *_: None)
    sources: dict[str, list[str]] = {}
    for pg in snap.pages:
        for link in pg.external_links:
            found = sources.setdefault(link, [])
            if len(found) < 3 and pg.url not in found:
                found.append(pg.url)
    unique = list(sources)
    todo = unique[: LIMITS.external_links_checked]
    started = time.monotonic()
    results: list[dict] = []
    slow: dict[str, int] = {}
    skipped_hosts = 0
    budget_exhausted = False
    for index, url in enumerate(todo, 1):
        cancel = getattr(gk, "cancel", None)
        if cancel is not None and cancel.is_set():
            raise ClaudiosError(E.SCAN_CANCELLED)
        if time.monotonic() - started > LIMITS.external_links_budget_seconds:
            budget_exhausted = True
            break
        host = (urlsplit(url).hostname or "").lower()
        report(url, index, len(todo))
        if slow.get(host, 0) >= SLOW_HOST_LIMIT:
            rec = _timeout_record(url)
            skipped_hosts += 1
        else:
            rec = await _check_guarded(gk, url)
            if rec["error"] == E.NET_TIMEOUT.value:
                slow[host] = slow.get(host, 0) + 1
        rec["sources"] = sources[url]
        results.append(rec)
    return {"results": results, "unique": len(unique), "checked": len(results),
            "budget_exhausted": budget_exhausted, "skipped_hosts": skipped_hosts}
