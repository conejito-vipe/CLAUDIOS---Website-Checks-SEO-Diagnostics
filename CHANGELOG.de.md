# Änderungsprotokoll

English version: [CHANGELOG.md](CHANGELOG.md)

## 0.2.0 (unveröffentlicht)

- **Oberfläche:** dunkles Design (Entwurf B): Symbolleiste mit Beschriftung und Logo, neuer Startscreen, Hilfe mit Inhaltsverzeichnis und gemeinsamer Suche, Wertungsring und Kategorie-Karten auf der Ergebnisseite, Erklärspalte neben der Befundliste.
- **Verwaltung:** Schnittstelle von CONEJITO (Admin): signierte Lizenzschlüssel (`CL1`) und signierte Schaltdatei (`SW1`, Ed25519, Prüfung offline, HTTPS-GET nur auf Knopfdruck). Neue Seite „Pro und Lizenz“, ausgeliefert inaktiv (kein Navigationseintrag, keine Sperren, keine Preise), bis die Verwaltung sie einschaltet. Öffentlicher Schlüssel, Adresse der Schaltdatei und der Pro-Schalter kommen nur aus der lokalen Datei `verwaltung.json` im Datenordner; Lizenzdaten gehören nie ins Repository (`.gitignore`, Repository-Test).
- **Sicherheit:** Die Browser-Skripte sperren jetzt lokale und interne Namen (`localhost.`, `*.localhost`, `*.lan`, `*.home.arpa`, Namen ohne Punkt) und jeden Host, dessen DNS-Antwort privat ist (Router, NAS, Cloud-Metadatenadresse), in allen vier Skripten gleich; der ZAP-API-Schlüssel wird in einer privaten Datei statt auf der Kommandozeile übergeben; Bildschirmfotos werden von der Platte gelöscht, wenn sich die DNS-Antwort während des Laufs geändert hat.
- **Installer und CI:** Dialog für Update, Reparatur und Zurückstellen wie bei CLAUDIA (nie bei stillen Updates), alte Programmdateien werden beim Update entfernt; Actions auf Commit-Hashes festgelegt; der Release-Ablauf testet zuerst und veröffentlicht Prüfsummen; CI auf Linux und Windows; wöchentliche Sicherheitsprüfung mit Gitleaks über die ganze Historie.

## 0.1.0 (unveröffentlicht)

- **Kern:** HTTPS-Gatekeeper mit DoH und IP-Bindung, Crawler (6 Ebenen), feste Grenzen, manipulationssicheres Scan-Protokoll mit Kontrollwert, Berichte.
- **Prüfungen:** HTML, Barrierefreiheit und Formulare, Sicherheits-Header und Cookies, `security.txt`, DNS- und E-Mail-Sicherheit (auch die MTA-STS-Richtliniendatei), Links, Takeover-Hinweise und Fingerprints, ads.txt, CORS, Cache-Control, Datenschutz und Qualität des Cookie-Banners, SEO (auch robots.txt im Detail, strukturierte Daten in der Tiefe, URL-Struktur, Klicktiefe, dünne Inhalte, Favicon, lokales SEO, Shops, internationales SEO), KI-Crawler und `llms.txt`, TLS-Zertifikat.
- **Werkzeug-Prüfungen:** W3C Nu Html Checker, W3C CSS Validator, ESLint, Stylelint, retire.js, sslyze (Protokolle, Cipher, Angriffstests der Stufe 2), Chromium-Prüfungen mit axe-core, optionaler Vergleich mit Firefox und WebKit, passives OWASP ZAP (Stufe 2).
- **Stufe 2:** Google-Anmeldung (Lesezugriff), Live-Prüfung der Property vor jedem Scan, Beleg für einen Host, 15 Minuten und einmal, Search-Console-Daten, feste Pfadliste, 12 Scans pro Domain und Tag.
- **Missbrauchsschutz:** strengere Eingaberegeln, Gesamtzeitbudget und Mindestpause für Browser, ZAP und sslyze, Erkennung von DNS-Rebinding, Verwerfen der Daten von Fremd-Hosts mit nicht öffentlicher Adresse, 30 s Abkühlzeit mit Countdown, 5 Scans pro Domain und Tag in Stufe 1.
- **Windows-Oberfläche (DE/EN):** Scan-Seite mit Stufenanzeige, Profilerklärungen, Experteneinstellungen für externe Dienste (vor jedem Scan erneut gefragt) und Scrollbalken, Befunde-Seite mit Filtern und Details, Export-Seite (CSV, Excel, PDF, ZIP mit Schwerpunkt-Prompt), optionaler Verlauf mit Vergleich, Seite „Externe Dienste“, Komponenten-Manager mit Prüfsummen, Entfernen mit Auswahl, Inno-Setup-Installer.
- **Optionale Dienste (standardmäßig aus):** RDAP-Domainablauf, Google Safe Browsing (eigener Schlüssel), PageSpeed Insights (eigener Schlüssel empfohlen); lokale Screenshots.
- **Windows-Build:** PyInstaller-Ordner-Build und Installer in der CI; eine feste Python-Laufzeit für sslyze im installierten Programm; ausdrückliches Einbinden der Module, die DNS über HTTPS braucht. Erster Test unter Windows 10 durchgeführt, Korrekturen laufen.
