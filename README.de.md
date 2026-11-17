<p align="center">
  <img src="assets/logo-full.png" alt="Claudios Logo" width="420">
</p>

# Claudios – Website Checks, SEO & Diagnostics

Freeware für Windows (Python): prüft eine Website auf sauberes HTML, CSS und JavaScript (W3C-Referenzen),
Sicherheit, Datenschutz und SEO. Jede Prüfung erklärt, *warum* sie wichtig ist.

*vipecoded with Claude (Anthropic) by fuhfux with love ❤️*

English: [README.en.md](README.en.md)

## Stand

Frühe Version. Die automatischen Tests (rund 125) laufen gegen **simulierte** Websites, DNS-Antworten und
Werkzeugausgaben. Das Verhalten in der Praxis (echte Websites, die echten W3C-Werkzeuge, der Installer) wird
noch geprüft. Ergebnisse sind technische Indizien, keine Zertifizierung und keine Rechtsberatung.

## Was geprüft wird

- **HTML / CSS / JS:** Dokumentstruktur, W3C Nu Html Checker, W3C CSS Validator, ESLint (Security-Plugin),
  Stylelint, retire.js, riskante Muster, Subresource Integrity, Inline-Handler
- **Sicherheit:** CSP, HSTS, Clickjacking, Referrer-Policy, Cookies, CORS, Cache-Control, Mixed Content,
  Geheimnisse im Quelltext, TLS-Zertifikat, TLS-Protokolle und Cipher (sslyze)
- **DNS und Mail:** SPF, DKIM, DMARC, CAA, MTA-STS, TLS-RPT, DNSSEC, Hinweise auf Subdomain-Takeover
- **SEO:** Titel, Beschreibung, Canonical, Robots, hreflang, Open Graph, strukturierte Daten, Sitemap, Soft-404, Links
- **Datenschutz:** Links auf Impressum und Datenschutzerklärung, externe Dienste, Cookies beim ersten Aufruf,
  Einwilligungslösung
- **Weiteres:** ads.txt, CMS-Erkennung, E-Mail-Adressen im Klartext

Das Handbuch im Programm nennt zu jeder Prüfung ein „Warum?“, die Technik-Doku zeigt die genauen Regeln und den Code.

## Sicherheit durch Design

- Nur HTTPS; Zertifikatsfehler brechen den Scan mit klarer Begründung ab
- Höchstens 6 Crawl-Ebenen; 25 Seiten (Selbstauskunft) bzw. 100 Seiten (Google-verifiziert); gedrosselt
- Eine Domain pro Scan; keine Kommandozeile, API, Massenabfrage, Plugins oder Telemetrie
- Passwörter, Cookie-Werte und Tokens werden nie gespeichert oder exportiert
- Aktive Prüfungen nur für verifizierte Domains (Stufe 2)
- Prüfungen, die nicht laufen konnten, stehen als „nicht ausgeführt“ im Bericht, nie als „bestanden“

Diese Schutzmaßnahmen verhindern versehentlichen Missbrauch. Wer den Quellcode verändert, wird davon nicht
aufgehalten. Nutze Claudios nur für eigene oder ausdrücklich freigegebene Websites.

## Entwicklung

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev,gui]"
    pytest

Programm starten: `python -m claudios`. Einen Windows-Installer baut der GitHub-Workflow
„Windows-Build und Installer“ (Installation für den aktuellen Benutzer, ohne Admin-Rechte).

## Mehr

[FAQ](FAQ.md) · [Sicherheitsrichtlinie](SECURITY.md) · [Mitwirken](CONTRIBUTING.md) ·
[Lizenzen Dritter](THIRD_PARTY_NOTICES.md) · [Änderungsprotokoll](CHANGELOG.md)

Lizenz: MIT für den Code. Das Logo ist ausgenommen (siehe `assets/ASSETS.md`). Freeware, keine Gewährleistung und
Haftung, soweit gesetzlich zulässig.
