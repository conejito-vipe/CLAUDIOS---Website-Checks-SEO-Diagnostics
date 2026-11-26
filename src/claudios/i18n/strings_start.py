"""UI-Texte des Startscreens (Scan-Seite: Titel, Untertext, Infokarte „So arbeitet CLAUDIOS“) und des Hilfe-Kopfs."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "doc.title": "Dokumentation – CLAUDIOS {version}",
    "doc.toc": "Inhaltsverzeichnis",
    "scan.title": "Website prüfen",
    "scan.subtitle": "Gib eine Adresse ein. CLAUDIOS prüft HTML, Sicherheit, Datenschutz, SEO und Barrierefreiheit und "
                     "erklärt zu jedem Befund, warum er wichtig ist.",
    "scan.info.title": "So arbeitet CLAUDIOS",
    "scan.info.1.h": "Eine Website, passiv",
    "scan.info.1.b": "Geprüft wird nur die Adresse, die du eingibst. In Stufe 1 gibt es ausschließlich passive Prüfungen "
                     "mit begrenzter Seitenzahl.",
    "scan.info.2.h": "Stufe 2 nur mit Nachweis",
    "scan.info.2.b": "Aktive Prüfungen, TLS-Angriffstests und Search-Console-Daten gibt es nur für Domains, die du "
                     "verifiziert hast.",
    "scan.info.3.h": "Online-Dienste sind aus",
    "scan.info.3.b": "Domainablauf, Safe Browsing und PageSpeed sind standardmäßig ausgeschaltet. Jedes Einschalten "
                     "fragt nach.",
    "scan.info.4.h": "Indizien, keine Zertifizierung",
    "scan.info.4.b": "Die Ergebnisse sind technische Hinweise und keine Rechtsberatung. Gespeichert wird ein Verlauf "
                     "nur, wenn du ihn einschaltest.",
})
TEXTS["en"].update({
    "doc.title": "Documentation – CLAUDIOS {version}",
    "doc.toc": "Table of contents",
    "scan.title": "Check a website",
    "scan.subtitle": "Enter an address. CLAUDIOS checks HTML, security, privacy, SEO and accessibility and explains why "
                     "each finding matters.",
    "scan.info.title": "How CLAUDIOS works",
    "scan.info.1.h": "One website, passive",
    "scan.info.1.b": "Only the address you enter is checked. Level 1 runs passive checks only, with a limited number "
                     "of pages.",
    "scan.info.2.h": "Level 2 needs proof",
    "scan.info.2.b": "Active checks, TLS attack tests and Search Console data are only available for domains you have "
                     "verified.",
    "scan.info.3.h": "Online services are off",
    "scan.info.3.b": "Domain expiry, Safe Browsing and PageSpeed are switched off by default. Switching one on asks "
                     "first.",
    "scan.info.4.h": "Indications, not certification",
    "scan.info.4.b": "Results are technical hints, not legal advice. A history is only stored if you switch it on.",
})
