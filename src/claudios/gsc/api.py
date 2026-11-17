"""Lesende Abfragen an die Search-Console-Schnittstellen (nur HTTPS). Abgefragt wird bei der Suchanalyse nur die
Dimension 'Seite', nie Suchbegriffe (keine personenbezogenen Suchanfragen)."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

import httpx

from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.redact import redact_url

SITES = "https://www.googleapis.com/webmasters/v3/sites"
INSPECT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
ROW_LIMIT = 1000


def new_client() -> httpx.Client:
    return httpx.Client(timeout=20.0, trust_env=False, follow_redirects=False)


def _call(http: httpx.Client, method: str, url: str, token: str, body: dict | None = None) -> dict:
    try:
        resp = http.request(method, url, headers={"Authorization": f"Bearer {token}"}, json=body)
    except httpx.HTTPError as exc:
        raise ClaudiosError(E.GOOGLE_AUTH, reason=type(exc).__name__) from None
    if resp.status_code >= 400:
        raise ClaudiosError(E.GOOGLE_AUTH, reason=f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        raise ClaudiosError(E.GOOGLE_AUTH, reason="invalid response") from None
    return data if isinstance(data, dict) else {}


def _int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def list_sites(http: httpx.Client, token: str) -> list[dict]:
    entries = _call(http, "GET", SITES, token).get("siteEntry")
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def top_pages(http: httpx.Client, token: str, site: str, today: date | None = None) -> tuple[list[dict], bool]:
    end = (today or date.today()) - timedelta(days=3)  # die Daten haben etwa 2 bis 3 Tage Verzug
    body = {"startDate": (end - timedelta(days=27)).isoformat(), "endDate": end.isoformat(),
            "dimensions": ["page"], "rowLimit": ROW_LIMIT}
    data = _call(http, "POST", f"{SITES}/{quote(site, safe='')}/searchAnalytics/query", token, body)
    raw = data.get("rows") if isinstance(data.get("rows"), list) else []
    rows = []
    for row in raw:
        keys = row.get("keys") if isinstance(row, dict) else None
        if keys and isinstance(keys[0], str):
            rows.append({"url": keys[0], "clicks": _int(row.get("clicks")), "impressions": _int(row.get("impressions"))})
    return rows, len(raw) >= ROW_LIMIT


def sitemaps(http: httpx.Client, token: str, site: str) -> list[dict]:
    data = _call(http, "GET", f"{SITES}/{quote(site, safe='')}/sitemaps", token)
    raw = data.get("sitemap") if isinstance(data.get("sitemap"), list) else []
    return [{"path": redact_url(str(s.get("path", "")))[:200], "errors": _int(s.get("errors")),
             "warnings": _int(s.get("warnings")), "pending": bool(s.get("isPending"))}
            for s in raw if isinstance(s, dict)]


def inspect(http: httpx.Client, token: str, site: str, url: str) -> dict:
    data = _call(http, "POST", INSPECT, token, {"inspectionUrl": url, "siteUrl": site})
    result = (data.get("inspectionResult") or {}).get("indexStatusResult") or {}
    return {"url": redact_url(url)[:200], "verdict": str(result.get("verdict", "")),
            "coverage": str(result.get("coverageState", ""))[:100], "robots": str(result.get("robotsTxtState", "")),
            "indexing": str(result.get("indexingState", "")), "fetch": str(result.get("pageFetchState", "")),
            "google_canonical": redact_url(str(result.get("googleCanonical", "")))[:200],
            "user_canonical": redact_url(str(result.get("userCanonical", "")))[:200]}
