"""UI-Texte für die Seite 'Export & Verlauf'."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.export": "Export & Verlauf",
    "exp.title": "Export und Verlauf",
    "exp.intro": "Speichere das Ergebnis als Tabelle oder PDF oder als ZIP für Claude mit einem Schwerpunkt. "
                 "Alle Dateien enthalten keine Passwörter, Cookie-Werte oder Tokens.",
    "exp.none": "Noch kein Ergebnis. Starte einen Scan.",
    "exp.current": "Aktueller Scan: {target} · Status: {status} · Gesamtwertung {score}/100",
    "exp.csv": "Befunde als CSV speichern …", "exp.xlsx": "Als Excel-Datei speichern …",
    "exp.pdf": "Als PDF speichern …",
    "exp.dialog_csv": "CSV speichern", "exp.dialog_xlsx": "Excel-Datei speichern", "exp.dialog_pdf": "PDF speichern",
    "exp.focus_lbl": "Schwerpunkt für die ZIP mit Prompt:",
    "exp.zip_focus": "ZIP für Claude mit Schwerpunkt exportieren …",
    "exp.focus.general": "Allgemein (alles)", "exp.focus.security": "Sicherheit", "exp.focus.seo": "SEO",
    "exp.focus.privacy": "Datenschutz", "exp.focus.accessibility": "Barrierefreiheit",
    "exp.focus.code": "Code-Qualität",
    "exp.hist.title": "Verlauf",
    "exp.hist.switch": "Zusammenfassungen der Scans speichern (Standard: an)",
    "exp.hist.info": "Gespeichert werden nur Prüfung, Schwere, Befundtext, Anzahl und Wertung, nie Adressen, Belege "
                     "oder Seiteninhalte, höchstens 20 je Domain, nur auf diesem Rechner.",
    "exp.hist.stored": "Gespeicherte Zusammenfassungen: {count}",
    "exp.hist.delete": "Gespeicherten Verlauf löschen …",
    "exp.hist.delete_ask": "Alle gespeicherten Zusammenfassungen endgültig löschen?",
    "exp.hist.deleted": "{count} Datei(en) gelöscht.",
    "exp.cmp.none": "Kein früherer Scan dieser Domain gespeichert. Schalte den Verlauf ein, dann gibt es beim "
                    "nächsten Scan einen Vergleich.",
    "exp.cmp.aborted": "Der Scan wurde abgebrochen und wird nicht verglichen oder gespeichert.",
    "exp.cmp.head": "Vergleich mit dem Scan vom {date}: Wertung {old} → {new} ({delta})",
    "exp.cmp.level_note": "Achtung: Stufe oder Profil unterscheiden sich, ein Teil der Unterschiede kommt daher.",
    "exp.cmp.new": "Neu ({count}):", "exp.cmp.resolved": "Behoben ({count}):",
    "exp.cmp.changed": "Andere Anzahl ({count}):", "exp.cmp.same": "Unverändert: {count}",
    "exp.cmp.more": "… und {count} weitere",
})
TEXTS["en"].update({
    "nav.export": "Export & history",
    "exp.title": "Export and history",
    "exp.intro": "Save the result as a table or PDF, or as a ZIP for Claude with a focus. "
                 "No file contains passwords, cookie values or tokens.",
    "exp.none": "No result yet. Start a scan.",
    "exp.current": "Current scan: {target} · Status: {status} · Overall score {score}/100",
    "exp.csv": "Save findings as CSV …", "exp.xlsx": "Save as Excel file …", "exp.pdf": "Save as PDF …",
    "exp.dialog_csv": "Save CSV", "exp.dialog_xlsx": "Save Excel file", "exp.dialog_pdf": "Save PDF",
    "exp.focus_lbl": "Focus for the ZIP with prompt:",
    "exp.zip_focus": "Export ZIP for Claude with focus …",
    "exp.focus.general": "General (everything)", "exp.focus.security": "Security", "exp.focus.seo": "SEO",
    "exp.focus.privacy": "Privacy", "exp.focus.accessibility": "Accessibility",
    "exp.focus.code": "Code quality",
    "exp.hist.title": "History",
    "exp.hist.switch": "Save summaries of the scans (default: on)",
    "exp.hist.info": "Only check, severity, finding text, count and score are stored, never addresses, evidence or "
                     "page content, at most 20 per domain, on this computer only.",
    "exp.hist.stored": "Stored summaries: {count}",
    "exp.hist.delete": "Delete stored history …",
    "exp.hist.delete_ask": "Delete all stored summaries permanently?",
    "exp.hist.deleted": "{count} file(s) deleted.",
    "exp.cmp.none": "No earlier scan of this domain is stored. Switch the history on and the next scan gets a "
                    "comparison.",
    "exp.cmp.aborted": "The scan was aborted and is neither compared nor stored.",
    "exp.cmp.head": "Comparison with the scan of {date}: score {old} → {new} ({delta})",
    "exp.cmp.level_note": "Note: level or profile differ, part of the differences comes from that.",
    "exp.cmp.new": "New ({count}):", "exp.cmp.resolved": "Fixed ({count}):",
    "exp.cmp.changed": "Different count ({count}):", "exp.cmp.same": "Unchanged: {count}",
    "exp.cmp.more": "… and {count} more",
})
