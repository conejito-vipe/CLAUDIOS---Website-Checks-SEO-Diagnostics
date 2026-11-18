# Sicherheitsrichtlinie

English version: [SECURITY.md](SECURITY.md)

## Schwachstelle melden

Nutze GitHub: **Security → Report a vulnerability** (private Meldung). Bitte keine öffentlichen Issues für Schwachstellen und keine Geheimnisse, Tokens oder personenbezogene Daten posten.

Ich kann keine Antwortzeiten versprechen; es ist ein Hobbyprojekt.

## Was zählt

- Umgehen der eingebauten Grenzen oder der Stufe-2-Verifizierung bei normaler Nutzung des Programms
- Passwörter, Cookie-Werte oder Tokens in Berichten, Protokollen oder Exporten
- Unsicherer Umgang mit heruntergeladenen Werkzeugen (Prüfsummen, Entpacken von Archiven)
- Einschleusen von Inhalten über eine geprüfte Website (Berichte, Oberfläche)

## Ehrliche Grenzen

Claudios ist Open Source. Die Schutzmaßnahmen (Limits, nur HTTPS, Verifizierungsstufen, Scan-Protokoll) verhindern versehentlichen oder bequemen Missbrauch, nicht entschlossene Änderungen am Code. Nur für eigene oder ausdrücklich freigegebene Systeme verwenden (vergleiche § 202c StGB und das Recht deines Landes). Keine Gewährleistung. Mehr: [THREAT_MODEL.de.md](THREAT_MODEL.de.md) und [docs/ABUSE_PROTECTION.de.md](docs/ABUSE_PROTECTION.de.md).

## Bekannte Lücken

- Windows-Build und Installer sind noch nicht auf echten Rechnern geprüft, ebenso wenig die Google-Anmeldung und der Kontrollwert des Scan-Protokolls im Windows-Anmeldeinformationsspeicher.
- sslyze wird aus dem Quellarchiv gebaut (bei PyPI gibt es kein Wheel); die Build-Werkzeuge dafür sind nicht per Prüfsumme gesichert.
- Browser, ZAP und sslyze öffnen eigene Verbindungen und nutzen die Drosselung von Claudios nicht. Es gelten ein Gesamtzeitbudget und eine Mindestpause, und Hosts, die sie selbst aufgelöst haben, werden danach erneut geprüft (erkannt, nicht verhindert).
- Die Browser-Downloads (Chromium, Firefox, WebKit) kommen vom Server von Playwright und sind nicht durch eine Prüfsumme von Claudios gesichert.
- Die Antwortformate von Safe Browsing und PageSpeed (mit gültigem Schlüssel) und die KI-Bot-Namen sind noch ungeprüft (siehe [docs/EXTERNAL_SERVICES.de.md](docs/EXTERNAL_SERVICES.de.md)).
- Installer und Programm sind nicht signiert; Windows SmartScreen kann warnen (siehe [FAQ](FAQ.de.md)).
