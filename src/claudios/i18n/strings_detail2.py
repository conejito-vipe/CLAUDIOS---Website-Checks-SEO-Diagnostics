"""UI-Texte der Befund-Erklärung, Teil 2: technische Angaben zum fehlenden Codefenster und fehlende Befund-Liste."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "detail.facts_result": "Technische Angaben: Scan-Stand nicht mehr vorhanden; gesucht wurde Zeile {line} der Adresse "
                           "{url}.",
    "detail.facts_source": "Technische Angaben: Zeile {line} der Adresse {url} wurde gesucht; im Scan gibt es {pages} "
                           "Seiten mit Text und {assets} gespeicherte Dateien, zum Beispiel {samples}.",
    "detail.facts_range": "Technische Angaben: Zeile {line} der Adresse {url} wurde gesucht; der gespeicherte Text hat "
                          "nur {lines} Zeilen.",
    "detail.nogroups": "Die Befund-Liste zu dieser Prüfung liegt nicht mehr vor; die Einzelheiten stammen deshalb nur "
                       "aus der Prüfbeschreibung.",
})
TEXTS["en"].update({
    "detail.facts_result": "Technical details: scan data no longer available; line {line} of {url} was looked up.",
    "detail.facts_source": "Technical details: line {line} of {url} was looked up; the scan holds {pages} pages with "
                           "text and {assets} stored files, for example {samples}.",
    "detail.facts_range": "Technical details: line {line} of {url} was looked up; the stored text has only {lines} "
                          "lines.",
    "detail.nogroups": "The findings list for this check is no longer available; the details therefore come only from "
                       "the check description.",
})
