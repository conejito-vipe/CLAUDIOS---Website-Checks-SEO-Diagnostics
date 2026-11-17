"""CSV-Import einer Seiten-Auswertung aus der Search Console (Export entpackt, Datei mit Seiten-Adressen).
Dateien mit Suchbegriffen werden abgelehnt. Gelesen werden nur Adresse, Klicks und Impressionen."""
from __future__ import annotations

import csv
import io
import re

from ..core.errors import ClaudiosError, ErrorCode as E

MAX_BYTES = 5_000_000
MAX_ROWS = 50_000
IMPRESSIONS = ("impressions", "impressionen")
CLICKS = ("clicks", "klicks")


def _number(value: str) -> int:
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else 0


def parse_pages_csv(data: bytes) -> list[dict]:
    if len(data) > MAX_BYTES:
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="file too large")
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="empty file")
    delimiter = max(",;\t", key=lines[0].count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header = [h.strip().lower() for h in rows[0]]
    imp = next((i for i, h in enumerate(header) if h in IMPRESSIONS), None)
    if imp is None:
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="no impressions column")
    clk = next((i for i, h in enumerate(header) if h in CLICKS), None)
    out = []
    for row in rows[1: MAX_ROWS + 1]:
        url = row[0].strip() if row else ""
        if len(row) <= imp or not url.lower().startswith("http") or "://" not in url:
            continue
        out.append({"url": url[:300], "impressions": _number(row[imp]),
                    "clicks": _number(row[clk]) if clk is not None and len(row) > clk else 0})
    if not out:
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="first column is not a list of page addresses")
    return out
