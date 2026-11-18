# Bedrohungsmodell

English version: [THREAT_MODEL.md](THREAT_MODEL.md)

Stand: nach den Paketen 6f bis 6n. Das Dokument beschreibt, was Claudios schützt, vor wem und wo die Grenzen liegen. Die Maßnahmen sind durch Tests abgesichert (`tests/test_policy.py`, `tests/test_security_policy.py`, `tests/test_hostile_input.py`, `tests/test_abuse_protection.py` und weitere), bisher aber nur gegen simulierte Daten. Die Schutzschichten stehen in [docs/ABUSE_PROTECTION.de.md](docs/ABUSE_PROTECTION.de.md), Dienste bei Dritten in [docs/EXTERNAL_SERVICES.de.md](docs/EXTERNAL_SERVICES.de.md).

## Was geschützt wird

| Gut | Warum wichtig |
|---|---|
| Fremde Server | Sie dürfen nicht angegriffen, überlastet oder ausgeforscht werden. |
| Geheimnisse des Nutzers | Google-Token, Client-Secret, API-Schlüssel für Safe Browsing. Passwörter und Cookie-Werte werden nie gespeichert. |
| Der Rechner des Nutzers | Heruntergeladene Werkzeuge führen Code aus. |
| Integrität der Berichte | Nicht ausgeführte Prüfungen dürfen nie als bestanden erscheinen. |

## Angreifer

| Angreifer | Ziel | Maßnahmen |
|---|---|---|
| **Missbraucher** (Nutzer, der fremde oder viele Seiten prüfen will) | Massen- oder Fremdscans, aktive Tests ohne Berechtigung | Eine Domain pro Scan, Tiefe 6, 25 oder 100 Seiten, Drosselung, Abkühlzeit, Stunden- und Tageslimits, manipulationssicheres Scan-Protokoll, nur HTTPS, keine privaten Adressen, keine Kommandozeile, kein Plugin-System. Aktive Prüfungen nur mit Stufe 2 (Search Console, Inhaber- oder Vollzugriff, vor jedem Scan live neu geprüft, Beleg für einen Host, 15 Minuten und einmal). |
| **Feindliche Website** | Programm blockieren, Berichte vergiften, Rechner angreifen | Alle Muster in linearer Zeit, Größen- und Zeitgrenzen, Maskierung aller Inhalte in der Oberfläche und im HTML-Bericht (CSP), Werkzeuge bekommen nur Dateien, nie Adressen, Browser mit gesperrten Service Workern und Anfragen nur über HTTPS an öffentliche Namen. |
| **Lieferkette** (manipulierter Download oder Paket) | Schadcode über Werkzeuge | Feste Versionen mit SHA256 oder Sperrdatei, sicheres Entpacken (kein Zip-Slip, keine Symlinks, Größenlimit), `npm ci --ignore-scripts`, `pip --require-hashes --no-deps`, nur Aktionen von GitHub selbst in den Workflows. Der Workflow „Sicherheitsprüfung“ prüft die festen Versionen auf bekannte Lücken. |
| **Anderes Programm auf dem Rechner** | Token abgreifen | Token nur im Arbeitsspeicher oder im Windows-Anmeldeinformationsspeicher, nie in Dateien, Protokollen oder ZIP-Dateien. Schwärzung beim Einlesen und vor dem Export. |

## Bewusst nicht geschützt

- **Wer den Quellcode ändert.** Claudios ist Open Source. Die Grenzen sind Reibung gegen Bequemlichkeit, kein Schutz gegen Entschlossene.
- **Ein Angreifer mit Administratorrechten** auf dem Rechner des Nutzers.
- **Ein gekapertes Konto** bei Google, npm, PyPI oder GitHub.
- **Die Browser-Downloads** (Chromium, Firefox, WebKit) von Playwright: Sie kommen von dessen Server über HTTPS und sind nicht durch eine eigene Prüfsumme von Claudios gesichert.
- **Nicht signierte Programmdatei:** Windows SmartScreen kann warnen.

## Restrisiken

- **Fremd-Hosts werden erkannt, nicht verhindert.** Chromium, Firefox, WebKit und ZAP lösen die Namen von Fremd-Hosts selbst auf. Zeigt ein Name auf eine nicht öffentliche Adresse, ist der Zugriff schon geschehen. Claudios löst jeden beobachteten Host danach erneut per DoH auf, verwirft seine Daten und meldet ihn (`BRW-FRN-001`).
- **Im ZAP-Lauf und im Firefox/WebKit-Lauf ist der Zielhost nicht an die geprüfte IP gebunden** (bei Chromium schon). Dort wird die Auflösung nur vor und nach dem Lauf geprüft (`core/rebind.py`).
- **Browser, ZAP und sslyze verbinden direkt** und kennen die Drosselung des Gatekeepers nicht. Je Scan gelten ein Gesamtzeitbudget (1.800 s), eine Mindestpause (15 s) und eine Höchstzahl an Läufen. Die Laufzeit des ZAP-Daemons selbst zählt nicht mit, nur das Browser-Skript durch ZAP.
- **Der Kontrollwert des Scan-Protokolls ist Reibung, kein Schutz.** Wer Protokoll und Kontrollwert löscht, sieht aus wie eine Neuinstallation. Das Schreiben des Kontrollwerts in den Windows-Anmeldeinformationsspeicher ist auf echten Rechnern noch nicht geprüft.
- **Der Beleg für Stufe 2 liegt im Arbeitsspeicher.** Wer den Quellcode ändert, kann ihn fälschen.
- **Safe Browsing und PageSpeed lösen Namen über das System auf**, nicht über DoH. Die Ziele sind zwei feste Google-Hosts, ohne Weiterleitung und mit Größenlimit.
- **Screenshots zeigen Seiteninhalt.** Sie bleiben lokal und werden nur auf Wunsch als ZIP gespeichert, aber nicht auf Geheimnisse geprüft.
- **PageSpeed lässt Google die Seite abrufen.** Das ist ein normaler Seitenaufruf durch einen Dritten, nur auf ausdrücklichen Wunsch.
- **Workflows referenzieren Aktionen per Versions-Tag**, nicht per Commit-Prüfsumme. Dependabot hält sie aktuell.
- **sslyze (AGPL-3.0) wird aus dem Quellarchiv gebaut**, die Build-Werkzeuge dafür sind nicht per Prüfsumme gesichert.
- **sslyze läuft mit einer neueren `cryptography`, als es selbst erlaubt.** Der Workflow „pip-Sperrliste“ erzwingt sie, weil die vom Paket erlaubte Version bekannte Lücken hat, und übernimmt sie nur nach einem erfolgreichen sslyze-Lauf gegen eine echte Seite. Das beweist nicht, dass jedes Zertifikat korrekt verarbeitet wird. Ein Fehler würde als „nicht ausgeführt“ sichtbar, nie als „bestanden“.
- **Die Git-Historie wird nicht automatisch nach Geheimnissen durchsucht**, nur der aktuelle Stand.
- **Befunde enthalten Text fremder Websites.** CSV- und Excel-Export neutralisieren Formel-Injektion; PDF- und HTML-Bericht maskieren alles.
- **Einige Formate sind noch ungeprüft:** das Antwortformat von Safe Browsing und PageSpeed mit gültigem Schlüssel, die KI-Bot-Namen und die Lizenzeinträge. Einmal auf einem GitHub-Rechner (Linux) bestätigt: die ZAP-Schnittstelle core/view/hosts, das RDAP-Format, die meisten Fingerprint-Texte und die Skripte shot_probe.jsundengine_probe.js mit echtem Chromium, Firefox und WebKit.

## Regelmäßige Prüfung

Der Workflow „Sicherheitsprüfung“ (`.github/workflows/security.yml`) läuft von Hand und wöchentlich: bandit für den Python-Code, pip-audit und npm audit für die Abhängigkeiten, außerdem erzeugt er eine Stückliste (SBOM). Meldungen stehen als Annotationen im Lauf.
