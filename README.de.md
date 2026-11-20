<p align="center">
  <img src="assets/logo-full.png" alt="CLAUDIOS Logo" width="420">
</p>

# CLAUDIOS – Website Checks, SEO & Diagnostics

English version: [README.md](README.md)

Freeware für Windows (Python): prüft eine einzelne Website auf sauberes HTML, CSS und JavaScript (W3C-Referenzen), Sicherheit, Datenschutz, SEO und Barrierefreiheit. Jede Prüfung erklärt, *warum* sie wichtig ist.

*vibecoded with Claude (Anthropic) by conejito-vipe with love ❤️*

## Stand

Frühe Version. Über 400 automatische Tests laufen gegen **simulierte** Websites, DNS-Antworten und Werkzeugausgaben. Windows-Build und Installer entstehen in der CI und hatten einen ersten Test unter Windows 10. Das Verhalten in der Praxis (echte Websites, die echten Werkzeuge, die Google-Anmeldung) wird noch geprüft. Ergebnisse sind technische Indizien, keine Zertifizierung und keine Rechtsberatung.

## Lizenz & Nutzung

CLAUDIOS wird öffentlich bereitgestellt, um es zu testen und weiterzuentwickeln. Die genauen Bedingungen regelt die [LICENSE](./LICENSE); die deutsche Fassung ist verbindlich.

- **Kostenlos nutzbar:** Privatpersonen (nicht kommerziell) sowie gemeinnützige Organisationen und Vereine (für gemeinnützige Zwecke), jeweils auf eigenen Systemen.
- **Keine kommerzielle Nutzung ohne Freigabe:** Unternehmen, Selbständige, Agenturen und Behörden müssen vorab über mein GitHub-Profil ([@conejito-vipe](https://github.com/conejito-vipe)) eine Freigabe bzw. Lizenz anfragen.
- **Keine Änderung, keine Weitergabe:** Die Software darf nicht verändert und nicht an Dritte weitergegeben werden, auch nicht unverändert. Der Quelltext ist zum Lesen und Prüfen da.
- **Ausschlüsse:** Politische Parteien sowie Vereine oder Gruppen, die vom Verfassungsschutz (Bund oder Land) als rechtsextremistische Bestrebung eingestuft oder verboten sind, sind von der Nutzung ausgeschlossen (Einzelheiten in der [LICENSE](./LICENSE)).

Ohne jegliche Gewährleistung oder Erfolgsgarantie.

## Was geprüft wird

- **HTML / CSS / JS:** Dokumentstruktur, doppelte IDs, Überschriften, Landmarks, Formulare, W3C Nu Html Checker, W3C CSS Validator, ESLint (Security-Plugin), Stylelint, retire.js, riskante Muster, Subresource Integrity, Inline-Handler
- **Sicherheit:** CSP, HSTS, Clickjacking, Referrer-Policy, Permissions-Policy, COOP/COEP/CORP, Cookies, CORS, Cache-Control, Mixed Content, Geheimnisse im Quelltext, `security.txt`, TLS-Zertifikat, TLS-Protokolle und Cipher (sslyze)
- **DNS und Mail:** SPF, DKIM, DMARC, CAA, MTA-STS (auch die Richtliniendatei), TLS-RPT, DNSSEC, Subdomain-Takeover (DNS und Fehlerseiten-Fingerprints)
- **SEO:** Titel, Beschreibung, Canonical, robots.txt (im Detail), hreflang und Sprachangaben, Open Graph, strukturierte Daten (in der Tiefe), Sitemap, Soft-404, Links, Komprimierung, Caching, dünne und doppelte Inhalte, URL-Struktur, Klicktiefe, Favicon, KI-Crawler, `llms.txt`, Vertrauenssignale, lokales SEO, Online-Shops
- **Datenschutz:** Links auf Impressum und Datenschutzerklärung, externe Dienste, Cookies beim ersten Aufruf, Einwilligungslösung und Qualität des Banners
- **Browser (Chromium über Playwright):** Konsolenfehler, Barrierefreiheit mit axe-core (WCAG 2.2), responsive Darstellung, Ladeleistung, nachgeladene Dienste; optional Vergleich mit Firefox und WebKit (Profil Tief)
- **Stufe 2 (nur verifizierte Domains):** frei erreichbare Dateien (feste Pfadliste), TLS-Angriffstests, passive Analyse mit OWASP ZAP, Search-Console-Daten
- **Optionale Online-Dienste (alle standardmäßig aus, Experteneinstellungen auf der Scan-Seite):** Domainablauf (RDAP), Google Safe Browsing (eigener Schlüssel), PageSpeed Insights; lokale Screenshots

Berichte: ZIP mit Prompt für Claude (allgemein oder mit Schwerpunkt Sicherheit, SEO, Datenschutz, Barrierefreiheit oder Code), CSV, Excel, PDF und ein optionaler Vergleich mit früheren Scans (wird nur gespeichert, wenn du es einschaltest).

Das Handbuch im Programm nennt zu jeder Prüfung ein „Warum?“, die Technik-Doku zeigt die genauen Regeln und den Code.

## Windows SmartScreen

Der Installer ist nicht signiert (Zertifikate kosten Geld). Windows SmartScreen zeigt deshalb „Der Computer wurde durch Windows geschützt“ und nennt den Herausgeber „Unbekannter Herausgeber“. So installierst du trotzdem:

1. Vergleiche die SHA256-Prüfsumme aus dem Build-Protokoll mit der heruntergeladenen Datei.
2. Klicke im SmartScreen-Fenster auf **Weitere Informationen** und dann auf **Trotzdem ausführen**.

Als Herausgeber steht im Installer und in der Liste der installierten Apps **GitHub - conejito-vipe**. Ein Name dort entfernt die SmartScreen-Warnung nicht, das kann nur ein Signaturzertifikat.

## Sicherheit durch Design

- Nur HTTPS; Zertifikatsfehler brechen den Scan mit klarer Begründung ab
- Höchstens 6 Crawl-Ebenen; bis zu 250 Seiten; gedrosselt
- Eine Domain pro Scan; Tages- und Stundenlimits, Abkühlzeit zwischen Scans und ein manipulationssicheres Scan-Protokoll
- Keine Kommandozeile, API, Massenabfrage, Plugins oder Telemetrie
- Passwörter, Cookie-Werte und Tokens werden nie gespeichert oder exportiert
- Aktive Prüfungen nur für verifizierte Domains (Stufe 2)
- Prüfungen, die nicht laufen konnten, stehen als „nicht ausgeführt“ im Bericht, nie als „bestanden“

Diese Schutzmaßnahmen verhindern versehentlichen Missbrauch. Wer den Quellcode verändert, wird technisch nicht aufgehalten; die Lizenz verbietet es. Nutze CLAUDIOS nur für eigene oder ausdrücklich freigegebene Websites. Einzelheiten: [docs/ABUSE_PROTECTION.de.md](docs/ABUSE_PROTECTION.de.md).

## Aus dem Quelltext bauen (für den eigenen Gebrauch, unverändert)

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev,gui]"
    pytest

Programm starten: `python -m claudios`. Einen Windows-Installer baut der GitHub-Workflow „Windows-Build und Installer“ (Installation für den aktuellen Benutzer, ohne Admin-Rechte). Den Installer oder den Quelltext weiterzugeben ist nicht erlaubt.

## Mehr

[FAQ](FAQ.de.md) · [Sicherheitsrichtlinie](SECURITY.de.md) · [Bedrohungsmodell](THREAT_MODEL.de.md) · [Rückmeldungen](CONTRIBUTING.de.md) · [Externe Dienste](docs/EXTERNAL_SERVICES.de.md) · [Google einrichten](docs/GOOGLE_SETUP.de.md) · [Lizenzen Dritter](THIRD_PARTY_NOTICES.de.md) · [Änderungsprotokoll](CHANGELOG.de.md) · [Lizenz](LICENSE.de.txt)

Das Logo gehört zum Werk und darf nur zusammen mit CLAUDIOS verwendet werden (siehe `assets/ASSETS.de.md`). Freeware, keine Gewährleistung und Haftung, soweit gesetzlich zulässig.
