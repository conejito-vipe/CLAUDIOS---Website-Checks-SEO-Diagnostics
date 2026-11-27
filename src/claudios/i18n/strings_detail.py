"""UI-Texte der Befund-Erklärung (Klick auf eine Zeile der Ergebnisliste)."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "detail.title": "Befund erklärt",
    "detail.hint": "Klicke auf eine Zeile: Erklärung und Lösung",
    "detail.found": "Was wurde gefunden",
    "detail.prev": "‹ Zurück", "detail.next": "Weiter ›",
    "detail.why": "Warum ist das wichtig",
    "detail.fix": "So behebst oder optimierst du es",
    "detail.method": "So prüft CLAUDIOS das",
    "detail.logic": "So wird bewertet",
    "detail.refs": "Mehr dazu",
    "detail.evidence": "Belege",
    "detail.where": "Betroffene Stellen",
    "detail.times": "{count}x",
    "detail.none": "Zu diesem Eintrag liegen keine Einzelheiten aus dem Scan vor.",
    "detail.nometa": "Zu dieser Prüfung gibt es keine Beschreibung.",
})
TEXTS["en"].update({
    "detail.title": "Finding explained",
    "detail.hint": "Click a row: explanation and fix",
    "detail.found": "What was found",
    "detail.prev": "‹ Previous", "detail.next": "Next ›",
    "detail.why": "Why it matters",
    "detail.fix": "How to fix or improve it",
    "detail.method": "How CLAUDIOS checks this",
    "detail.logic": "How it is rated",
    "detail.refs": "More information",
    "detail.evidence": "Evidence found",
    "detail.where": "Affected places",
    "detail.times": "{count}x",
    "detail.none": "The scan holds no details for this entry.",
    "detail.nometa": "There is no description for this check.",
})
