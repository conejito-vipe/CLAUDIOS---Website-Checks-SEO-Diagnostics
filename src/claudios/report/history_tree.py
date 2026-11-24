"""Der Verlauf nach Website und Tag gruppiert (nur Zusammenfassungen, nie Adressen oder Belege)."""
from __future__ import annotations

from datetime import datetime

from . import history


def local_parts(saved: str) -> tuple[str, str]:
    """(Tag, Uhrzeit) in der Ortszeit; bei unlesbarer Zeit der Anfang der gespeicherten Zeichenkette."""
    try:
        when = datetime.fromisoformat(saved).astimezone()
    except ValueError:
        return saved[:10], saved[11:16]
    return when.strftime("%Y-%m-%d"), when.strftime("%H:%M")


def grouped() -> list[tuple[str, list[tuple[str, list[tuple[str, dict]]]]]]:
    """[(Website, [(Tag, [(Uhrzeit, Eintrag)])])]: Websites A bis Z, Tage und Scans neueste zuerst."""
    folder = history.history_dir()
    tree: dict[str, dict[str, list[tuple[str, dict]]]] = {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        record = history.load(path)
        if record is None:
            continue
        day, clock = local_parts(str(record["saved"]))
        tree.setdefault(str(record.get("host") or "?"), {}).setdefault(day, []).append((clock, record))
    result = []
    for host in sorted(tree):
        days = []
        for day, scans in sorted(tree[host].items(), reverse=True):
            days.append((day, sorted(scans, key=lambda item: str(item[1]["saved"]), reverse=True)))
        result.append((host, days))
    return result
