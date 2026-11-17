# Threat model / Bedrohungsmodell

Status: Stand nach Paket 6d. Beschreibt, was Claudios schützt, vor wem und wo die Grenzen liegen. Die Maßnahmen sind
durch Tests abgesichert (`tests/test_policy.py`, `tests/test_security_policy.py`, `tests/test_hostile_input.py`),
aber bisher nur gegen simulierte Daten. / Describes what Claudios protects, against whom and where the limits are.

## Was geschützt wird / Assets

| Gut | Warum wichtig |
|---|---|
| Fremde Server | Sie dürfen nicht angegriffen, überlastet oder ausgeforscht werden. |
| Geheimnisse des Nutzers | Google-Token, Client-Secret, später API-Schlüssel. Passwörter und Cookie-Werte nie speichern. |
| Der Rechner des Nutzers | Heruntergeladene Werkzeuge führen Code aus. |
| Integrität der Berichte | Nicht ausgeführte Prüfungen dürfen nie als bestanden erscheinen. |

## Angreifer / Actors

| Angreifer | Ziel | Maßnahmen |
|---|---|---|
| **Missbraucher** (Nutzer, der fremde oder viele Seiten prüfen will) | Massen- oder Fremdscans, aktive Tests ohne Berechtigung | Eine Domain pro Scan, Tiefe 6, 25 oder 100 Seiten, Drosselung, Abkühlzeit und Stundenlimit, nur HTTPS, keine privaten Adressen, keine Kommandozeile, kein Plugin-System. Aktive Prüfungen nur mit Stufe 2 (Search Console, Inhaber- oder Vollzugriff, bei jedem Scan neu geprüft). |
| **Feindliche Website** | Programm blockieren, Berichte vergiften, Rechner angreifen | Alle Muster in linearer Zeit, Größen- und Zeitgrenzen, Maskierung aller Inhalte in der Oberfläche und im HTML-Bericht (CSP), Werkzeuge bekommen nur Dateien, nie Adressen, Browser mit gesperrten Service Workern und Anfragen nur über HTTPS an öffentliche Namen. |
| **Lieferkette** (manipulierter Download oder Paket) | Schadcode über Werkzeuge | Feste Versionen mit SHA256 oder Sperrdatei, sicheres Entpacken (kein Zip-Slip, keine Symlinks, Größenlimit), `npm ci --ignore-scripts`, `pip --require-hashes --no-deps`, nur Aktionen von GitHub selbst in den Workflows. |
| **Anderes Programm auf dem Rechner** | Token abgreifen | Token nur im Arbeitsspeicher oder im Windows-Anmeldeinformationsspeicher, nie in Dateien, Protokollen oder ZIP-Dateien. Schwärzung beim Einlesen und vor dem Export. |

## Bewusst nicht geschützt / Not protected

- **Wer den Quellcode ändert.** Claudios ist Open Source. Die Grenzen sind Reibung gegen Bequemlichkeit, kein
  Schutz gegen Entschlossene.
- **Ein Angreifer mit Administratorrechten** auf dem Rechner des Nutzers.
- **Ein gekapertes Konto** bei Google, npm, PyPI oder GitHub.
- **Der Chromium-Download** von Playwright: Er kommt von dessen Server über HTTPS und ist nicht durch eine eigene
  Prüfsumme von Claudios gesichert.
- **Nicht signierte Programmdatei:** Windows SmartScreen kann warnen.

## Bekannte Restrisiken / Residual risks

- Browser, ZAP und sslyze verbinden direkt und kennen die Drosselung des Gatekeepers nicht (Zeitlimit je Lauf, kein
  Gesamtbudget). Geplant in 6f.
- Diese Programme lösen Namen selbst auf. DNS-Rebinding zwischen Prüfung und Lauf ist denkbar (6f).
- Die Verifizierung für Stufe 2 wird als Zeichenkette an den Scan übergeben. Ein Beleg mit Host und Ablaufzeit
  ist geplant (6f).
- Das Audit-Protokoll erkennt Änderungen, aber nicht das Löschen der ganzen Datei (6f).
- Workflows referenzieren Aktionen per Versions-Tag, nicht per Commit-Prüfsumme. Dependabot hält sie aktuell.
- sslyze (AGPL-3.0) wird aus dem Quellarchiv gebaut, die Build-Werkzeuge dafür sind nicht per Prüfsumme gesichert.
- Die Git-Historie wird nicht automatisch nach Geheimnissen durchsucht, nur der aktuelle Stand.

## Regelmäßige Prüfung / Routine checks

Der Workflow „Sicherheitsprüfung“ (`.github/workflows/security.yml`) läuft von Hand und wöchentlich: bandit für den
Python-Code, pip-audit und npm audit für die Abhängigkeiten, außerdem erzeugt er eine Stückliste (SBOM).
Meldungen stehen als Annotationen im Lauf.
