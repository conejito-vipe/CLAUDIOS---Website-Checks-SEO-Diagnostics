"""Quelltext für das Codefenster: gespeicherte CSS- und JavaScript-Dateien (Probe 'assets') und HTML-Seiten.
Inline-Skripte und Inline-Stile liegen im HTML der Seite, ihre Zeilennummern zählen aber ab dem Anfang des Blocks.
Für Prüfungen mit der ID JSS- oder CSS- wird deshalb nie die Seite gezeigt (es stünde die falsche Zeile im Fenster)."""
from __future__ import annotations

from ..core.redact import redact_url

INLINE_PREFIXES = ("JSS-", "CSS-")


def _same(stored: str, url: str) -> bool:
    return stored == url or redact_url(stored) == url


def asset_text(result, urls) -> tuple[str, str] | None:
    extra = getattr(getattr(result, "snapshot", None), "extra", None)
    assets = extra.get("assets") if isinstance(extra, dict) else None
    if not isinstance(assets, dict):
        return None
    for url in urls:
        for kind in ("css", "js"):
            for item in assets.get(kind) or []:
                if not isinstance(item, dict) or item.get("status") != 200 or not item.get("text"):
                    continue
                if _same(str(item.get("url") or ""), str(url)):
                    return str(item["url"]), str(item["text"])
    return None


def page_html(result, urls) -> tuple[str, str] | None:
    pages = getattr(getattr(result, "snapshot", None), "pages", None) or []
    for url in urls:
        for page in pages:
            body = getattr(page, "html", None)
            if body and _same(page.url, str(url)):
                return page.url, body
    return None


def source_for(result, urls, check_id: str = "") -> tuple[str, str] | None:
    """(Adresse, Text) der Datei, auf die sich 'Line N' im Beleg bezieht, sonst None."""
    found = asset_text(result, urls)
    if found is not None:
        return found
    if check_id.startswith(INLINE_PREFIXES):
        return None
    return page_html(result, urls)
