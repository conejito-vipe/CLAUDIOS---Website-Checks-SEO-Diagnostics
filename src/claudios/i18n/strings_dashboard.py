"""UI-Texte der Seite „Dashboard“ (Entwicklung je Domain, Ort der Bildschirmfotos)."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.dashboard": "Dashboard",
    "dash.title": "Dashboard",
    "dash.intro": "Entwicklung deiner bisherigen Prüfungen, getrennt nach Domain. Grundlage sind die gespeicherten "
                  "Zusammenfassungen (Export & Verlauf).",
    "dash.empty": "Noch keine gespeicherten Scans. Nach dem nächsten Scan erscheint hier die Entwicklung.",
    "dash.col.when": "Zeitpunkt", "dash.col.score": "Gesamtwertung", "dash.col.change": "Veränderung",
    "dash.col.findings": "Fehler und Warnungen",
    "dash.cat": "{name}: {first} → {last} ({delta})",
    "dash.need_two": "Für eine Entwicklung braucht es mindestens zwei Scans dieser Domain.",
    "dash.shots": "Bildschirmfotos (wenn aktiviert) werden automatisch hier gespeichert: {path}",
    "dash.open": "Ordner mit den Bildschirmfotos öffnen",
})
TEXTS["en"].update({
    "nav.dashboard": "Dashboard",
    "dash.title": "Dashboard",
    "dash.intro": "How your past checks developed, grouped by domain. Based on the saved summaries (Export & history).",
    "dash.empty": "No saved scans yet. The development appears here after the next scan.",
    "dash.col.when": "Time", "dash.col.score": "Overall score", "dash.col.change": "Change",
    "dash.col.findings": "Errors and warnings",
    "dash.cat": "{name}: {first} → {last} ({delta})",
    "dash.need_two": "A development needs at least two scans of this domain.",
    "dash.shots": "Screenshots (when enabled) are saved automatically here: {path}",
    "dash.open": "Open the screenshot folder",
})
