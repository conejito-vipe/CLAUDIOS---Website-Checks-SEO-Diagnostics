"""Gemeinsame Bausteine für CSV, Excel und PDF: Tabellen aus dem bereinigten Bericht (build_report), Schutz gegen
Formel-Injektion und eine letzte Prüfung auf erkennbare Geheimnisse. In CSV und Excel bleiben Zahlen echte Zahlen
(ohne Tausendertrenner); nur das PDF formatiert sie nach Sprache."""
from __future__ import annotations

from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.redact import find_leaks

DANGEROUS = ("=", "+", "-", "@", "\t", "\r")

SEVERITY = {"de": ("Info", "Hinweis", "Warnung", "Fehler", "Kritisch"),
            "en": ("Info", "Note", "Warning", "Error", "Critical")}
STATUS = {"de": {"complete": "vollständig", "limited": "mit Einschränkungen", "aborted": "abgebrochen"},
          "en": {"complete": "complete", "limited": "with limitations", "aborted": "aborted"}}

LABELS = {
    "de": {
        "report": "Claudios-Bericht", "sev": "Schwere", "check": "Prüfung", "cnt": "Anzahl", "msg": "Befund",
        "evidence": "Beleg", "ex": "Beispiele", "id": "ID", "title": "Titel", "status": "Status",
        "url": "Adresse", "depth": "Ebene", "ms": "Antwortzeit (ms)", "bytes": "Daten (Bytes)", "error": "Fehler",
        "key": "Angabe", "value": "Wert", "target": "Adresse der Website", "level": "Stufe", "profile": "Profil",
        "started": "Beginn", "finished": "Ende", "pages": "Seiten geprüft", "requests": "Anfragen",
        "data": "Daten", "score": "Gesamtwertung", "category": "Kategorie", "abort": "Abbruch",
        "notrun": "Nicht ausgeführt", "none": "Keine Befunde.",
        "disc": "Technische Indizien, keine Rechtsberatung. Orientierungswert, kein Gütesiegel.",
        "s_summary": "Übersicht", "s_findings": "Befunde", "s_checks": "Prüfungen", "s_pages": "Seiten",
    },
    "en": {
        "report": "Claudios report", "sev": "Severity", "check": "Check", "cnt": "Count", "msg": "Finding",
        "evidence": "Evidence", "ex": "Examples", "id": "ID", "title": "Title", "status": "Status",
        "url": "Address", "depth": "Level", "ms": "Response time (ms)", "bytes": "Data (bytes)", "error": "Error",
        "key": "Item", "value": "Value", "target": "Website address", "level": "Level", "profile": "Profile",
        "started": "Started", "finished": "Finished", "pages": "Pages checked", "requests": "Requests",
        "data": "Data", "score": "Overall score", "category": "Category", "abort": "Abort",
        "notrun": "Not executed", "none": "No findings.",
        "disc": "Technical indications, not legal advice. Orientation value, not a certification.",
        "s_summary": "Summary", "s_findings": "Findings", "s_checks": "Checks", "s_pages": "Pages",
    },
}


def safe_cell(value):
    """Text, der in Tabellenprogrammen als Formel gelten könnte, bekommt ein ' davor. Zahlen bleiben Zahlen."""
    if isinstance(value, str) and value.startswith(DANGEROUS):
        return "'" + value
    return value


def finding_table(rep: dict, lang: str) -> tuple[list, list[list]]:
    labels = LABELS[lang]
    header = [labels["sev"], labels["check"], labels["cnt"], labels["msg"], labels["evidence"], labels["ex"]]
    rows = [[SEVERITY[lang][g["severity"]], g["check_id"], g["count"], g["msg_" + lang], g["evidence"],
             " ".join(g["example_urls"])] for g in rep["findings"]]
    return header, rows


def check_table(rep: dict, lang: str) -> tuple[list, list[list]]:
    labels = LABELS[lang]
    header = [labels["id"], labels["title"], labels["status"]]
    return header, [[c["id"], c["title_" + lang], c["status"]] for c in rep["checks"]]


def page_table(rep: dict, lang: str) -> tuple[list, list[list]]:
    labels = LABELS[lang]
    header = [labels["url"], labels["status"], labels["depth"], labels["ms"], labels["bytes"], labels["error"]]
    rows = [[p["url"], p["status"], p["depth"], p["elapsed_ms"], p["bytes"], p["error"] or ""] for p in rep["pages"]]
    return header, rows


def summary_table(rep: dict, lang: str) -> tuple[list, list[list]]:
    labels, sc = LABELS[lang], rep["scan"]
    rows = [[labels["target"], sc["target"]], [labels["status"], STATUS[lang].get(sc["status"], sc["status"])],
            [labels["level"], sc["level"]], [labels["profile"], sc["profile"]],
            [labels["started"], sc["started"]], [labels["finished"], sc["finished"]],
            [labels["pages"], sc["pages_checked"]], [labels["requests"], sc["requests"]],
            [labels["bytes"], sc["bytes"]], [labels["score"], rep["scores"]["overall"]]]
    for category, value in rep["scores"]["categories"].items():
        rows.append([f"{labels['category']} {category}", value])
    if sc["abort"]:
        info = sc["abort"][lang]
        rows.append([labels["abort"], f"{info['title']}: {info['cause']}"])
    return [labels["key"], labels["value"]], rows


def ensure_clean(*tables: tuple[list, list[list]]) -> None:
    """Letzte Schranke: nichts Erkennbares (Schlüssel, Tokens) darf in einer Exportdatei stehen."""
    cells: list[str] = []
    for header, rows in tables:
        cells.extend(str(cell) for cell in header)
        for row in rows:
            cells.extend(str(cell) for cell in row)
    leaks = find_leaks("\n".join(cells))
    if leaks:
        raise ClaudiosError(E.EXPORT_FAILED, reason=f"possible secret in the export: {leaks[0]}")
