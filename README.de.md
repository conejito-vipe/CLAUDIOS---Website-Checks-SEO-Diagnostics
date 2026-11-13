# Claudios – Website Checks, SEO & Diagnostics

Freeware für Windows (Python): prüft Websites auf sauberes HTML/CSS/JS (W3C-Referenzen),
Sicherheit, Datenschutz, SEO und Barrierefreiheit. Jede Prüfung erklärt, *warum* sie wichtig ist.

*vipecoded with Claude (Anthropic) by fuhfux with love ❤️ – nicht mit Anthropic verbunden.*

## Sicherheit durch Design
- Nur HTTPS; Zertifikatsfehler brechen den Scan mit klarer Begründung ab
- Max. 6 Crawl-Ebenen, 25 Seiten (unverifiziert) bzw. 100 Seiten (verifiziert), gedrosselt
- Eine Domain pro Scan; keine CLI/API/Massenabfrage, keine Plugins, keine Telemetrie
- Passwörter, Cookie-Werte und Tokens werden nie gespeichert oder exportiert
- Aktive Prüfungen nur für per Google Search Console verifizierte Domains

## Entwicklung
    py -3.12 -m venv .venv && .venv\Scripts\activate
    pip install -e .[dev]
    pytest

Nur für eigene oder ausdrücklich freigegebene Websites. Ergebnisse sind technische Indizien,
keine Rechtsberatung. Siehe SECURITY.md. Keine Gewährleistung.
