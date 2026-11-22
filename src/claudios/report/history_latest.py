"""Der zuletzt gespeicherte Scan über alle Domains (für die Ergebnisseite nach einem Neustart)."""
from __future__ import annotations

from . import history


def latest_overall() -> dict | None:
    folder = history.history_dir()
    best: dict | None = None
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        record = history.load(path)
        if record is not None and (best is None or record["saved"] > best["saved"]):
            best = record
    return best
