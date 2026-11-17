"""Search-Console-Daten für den Scan. Mit CSV-Import (jede Stufe) oder über die Schnittstelle (nur Stufe 2 und nur
für die live geprüfte Property). Im Ergebnis stehen nur Adressen, Zahlen und Statuswerte, keine Suchbegriffe."""
from __future__ import annotations

import asyncio
import time

from ..gsc import api, session
from .errors import ClaudiosError

NAME = "gsc"
MIN_LEVEL = 1
INSPECT_MAX = 10
PAGES_MAX = 5000


def _pause(seconds: float) -> None:
    time.sleep(seconds)


def _api(snap) -> dict | None:
    from ..checks._browser import sample_urls  # erst hier importiert: die Prüfungen laden die Probes, nicht umgekehrt

    state = session.SESSION
    verified = state.last_verified
    if snap.level < 2 or not state.use_data or verified is None or verified[0] != snap.target.host:
        return None
    site = verified[1]
    out: dict = {"error": None, "pages": None, "truncated": False, "sitemaps": None, "inspections": None}
    http = api.new_client()
    try:
        try:
            token = state.access_token(http)
        except ClaudiosError as exc:
            out["error"] = exc.code.value
            return out
        try:
            out["pages"], out["truncated"] = api.top_pages(http, token, site)
        except ClaudiosError as exc:
            out["error"] = exc.code.value
        try:
            out["sitemaps"] = api.sitemaps(http, token, site)
        except ClaudiosError as exc:
            out["error"] = out["error"] or exc.code.value
        done: list[dict] = []
        failed = False
        for url in sample_urls(snap)[:INSPECT_MAX]:
            try:
                done.append(api.inspect(http, token, site, url))
            except ClaudiosError as exc:
                out["error"], failed = out["error"] or exc.code.value, True
                break
            _pause(1.0)
        if done or not failed:
            out["inspections"] = done
    finally:
        http.close()
    return out


async def collect(gk, snap, resolver) -> dict:
    api_data = await asyncio.to_thread(_api, snap)
    pages, source, truncated = None, None, False
    if api_data and api_data["pages"] is not None:
        pages, source, truncated = api_data["pages"], "api", api_data["truncated"]
    elif session.SESSION.csv_pages:
        pages, source = list(session.SESSION.csv_pages), "csv"
    return {"source": source, "pages": pages[:PAGES_MAX] if pages else pages, "truncated": truncated,
            "api": api_data}
