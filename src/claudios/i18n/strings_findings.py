"""UI-Texte für die Seite 'Befunde'."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.findings": "Befunde",
    "fnd.all": "Alle Schweregrade", "fnd.min": "ab {sev}", "fnd.cat_all": "Alle Kategorien",
    "fnd.search": "In den Befunden suchen …", "fnd.notrun": "Nicht ausgeführte Prüfungen zeigen",
    "fnd.count": "{shown} von {total} Einträgen", "fnd.state": "nicht ausgeführt",
    "fnd.none": "Keine Treffer für diesen Filter.", "fnd.severity": "Schwere", "fnd.occurrences": "Anzahl",
    "fnd.finding": "Befund", "fnd.evidence": "Beleg", "fnd.pages": "Betroffene Seiten",
    "fnd.more": "… und {count} weitere", "fnd.status": "Status",
})
TEXTS["en"].update({
    "nav.findings": "Findings",
    "fnd.all": "All severities", "fnd.min": "{sev} and above", "fnd.cat_all": "All categories",
    "fnd.search": "Search the findings …", "fnd.notrun": "Show checks that did not run",
    "fnd.count": "{shown} of {total} entries", "fnd.state": "not executed",
    "fnd.none": "No matches for this filter.", "fnd.severity": "Severity", "fnd.occurrences": "Count",
    "fnd.finding": "Finding", "fnd.evidence": "Evidence", "fnd.pages": "Affected pages",
    "fnd.more": "… and {count} more", "fnd.status": "Status",
})
