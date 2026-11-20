"""Hinweis zum Scan-Protokoll im Export-Dialog. Der Dateiname sortiert hinter allen anderen strings_*.py, damit der Satz an den
endgültigen Text von export.text angehängt wird (die Sperrzeit kommt aus limits.py)."""
from __future__ import annotations

from ..core.limits import LIMITS
from .strings import TEXTS

HOURS = LIMITS.audit_tamper_lock_seconds // 3600

NOTE = {
    "de": ("Hinweis: Das Scan-Protokoll (Datei audit.jsonl im Ordner logs) gehört nicht zum Export. Ändere, ersetze "
           "oder lösche es nicht von Hand und kopiere es nur zur Sicherung. Sonst sperrt der Missbrauchsschutz neue "
           f"Scans für {HOURS} Stunden."),
    "en": ("Note: The scan log (file audit.jsonl in the logs folder) is not part of the export. Do not edit, replace or "
           "delete it by hand and copy it only as a backup. Otherwise the abuse protection blocks new scans for "
           f"{HOURS} hours."),
}

for _lang, _note in NOTE.items():
    TEXTS[_lang]["export.text"] = TEXTS[_lang]["export.text"] + "\n\n" + _note
