# Änderungsprotokoll

English version: [CHANGELOG.md](CHANGELOG.md)

## 0.1.0 (unveröffentlicht)

- **Kern:** HTTPS-Gatekeeper mit DoH und IP-Bindung, Crawler (6 Ebenen), feste Grenzen, manipulationssicheres Scan-Protokoll mit Kontrollwert, Berichte.
- **Prüfungen:** HTML, Barrierefreiheit und Formulare, Sicherheits-Header und Cookies, `security.txt`, DNS- und E-Mail-Sicherheit (auch die MTA-STS-Richtliniendatei), Links, Takeover-Hinweise und Fingerprints, ads.txt, CORS, Cache-Control, Datenschutz und Qualität des Cookie-Banners, SEO (auch robots.txt im Detail, strukturierte Daten in der Tiefe, URL-Struktur, Klicktiefe, dünne Inhalte, Favicon, lokales SEO, Shops, internationales SEO), KI-Crawler und `llms.txt`, TLS-Zertifikat.
- **Werkzeug-Prüfungen:** W3C Nu Html Checker, W3C CSS Validator, ESLint, Stylelint, retire.js, sslyze (Protokolle, Cipher, Angriffstests der Stufe 2), Chromium-Prüfungen mit axe-core, optionaler Vergleich mit Firefox und WebKit, passives OWASP ZAP (Stufe 2).
- **Stufe 2:** Google-Anmeldung (Lesezugriff), Live-Prüfung der Property vor jedem Scan, Beleg für einen Host, 15 Minuten und einmal, Search-Console-Daten, feste Pfadliste, 10 Scans pro Domain und Tag.
- **Missbrauchsschutz:** strengere Eingaberegeln, Gesamtzeitbudget und Mindestpause für Browser, ZAP und sslyze, Erkennung von DNS-Rebinding, Verwerfen der Daten von Fremd-Hosts mit nicht öffentlicher Adresse.
- **Windows-Oberfläche (DE/EN):** Scan-Seite mit Stufenanzeige, Befunde-Seite mit Filtern und Details, Export-Seite (CSV, Excel, PDF, ZIP mit Schwerpunkt-Prompt), optionaler Verlauf mit Vergleich, Seite „Externe Dienste“, Komponenten-Manager mit Prüfsummen, Entfernen mit Auswahl, Inno-Setup-Installer.
- **Optionale Dienste (standardmäßig aus):** RDAP-Domainablauf, Google Safe Browsing (eigener Schlüssel), PageSpeed Insights; lokale Screenshots.
- **Windows-Build:** PyInstaller-Ordner-Build und Installer in der CI; eine feste Python-Laufzeit für sslyze im installierten Programm (auf echten Rechnern noch nicht geprüft).
