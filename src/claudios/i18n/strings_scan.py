"""UI-Texte der Scan-Seite für Stufe 1 und Stufe 2 (überschreibt scan.google aus strings.py)."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "scan.google": "Mit Google verifizieren (Stufe 2) …",
    "scan.level1": "Stufe 1 (Selbstauskunft): höchstens {pages} Seiten und {depth} Ebenen, nur passive Prüfungen. "
                   "Aktive Prüfungen und die Search Console gibt es mit Stufe 2 (Seite Search Console).",
    "scan.level_armed": "Stufe 2 ist eingeschaltet: Scans von Domains in deinen Properties laufen mit Stufe 2 "
                        "(höchstens {pages} Seiten und {depth} Ebenen, mit aktiven Prüfungen).",
    "scan.level2": "Stufe 2 (verifiziert über {prop}): höchstens {pages} Seiten und {depth} Ebenen, mit aktiven "
                   "Prüfungen und Search-Console-Daten. Die Berechtigung wird vor dem Scan live geprüft.",
    "scan.level_nomatch": "Stufe 2 ist eingeschaltet, aber keine deiner Properties mit Inhaber- oder Vollzugriff "
                          "deckt diese Domain ab. Der Scan würde abgelehnt.",
    "scan.done_level": "Scan beendet: {status} (Stufe {level}).",
})
TEXTS["en"].update({
    "scan.google": "Verify with Google (level 2) …",
    "scan.level1": "Level 1 (self-declaration): at most {pages} pages and {depth} levels, passive checks only. "
                   "Active checks and Search Console are available with level 2 (Search Console page).",
    "scan.level_armed": "Level 2 is on: scans of domains in your properties run with level 2 "
                        "(at most {pages} pages and {depth} levels, with active checks).",
    "scan.level2": "Level 2 (verified via {prop}): at most {pages} pages and {depth} levels, with active checks "
                   "and Search Console data. The authorisation is checked live before the scan.",
    "scan.level_nomatch": "Level 2 is on, but none of your properties with owner or full access covers this "
                          "domain. The scan would be refused.",
    "scan.done_level": "Scan finished: {status} (level {level}).",
})
