# Externe Dienste in CLAUDIOS

English version: [EXTERNAL_SERVICES.md](EXTERNAL_SERVICES.md)

CLAUDIOS spricht grundsätzlich nur mit der geprüften Website. Dienste, die Daten an Dritte senden, sind **standardmäßig aus** und lassen sich auf der Seite „Externe Dienste“ einzeln einschalten (jeweils mit Rückfrage). Der Schalter steht in `config/services.json` (nur „Dienst: an/aus“, keine Schlüssel, keine Adressen). Lokale Optionen (Screenshots) stehen in `config/options.json`.

| Dienst | Wohin | Was wird gesendet | Was sieht der Dritte |
|---|---|---|---|
| RDAP (Domainablauf) | `data.iana.org`, dann der RDAP-Server der Endung | die registrierbare Domain | IP-Adresse, User-Agent |
| Safe Browsing | `safebrowsing.googleapis.com` | bis zu 5 Adressen der Website ohne Parameter, dazu dein API-Schlüssel | IP-Adresse, die Adressen |
| PageSpeed Insights | `www.googleapis.com` | die Adresse der Startseite, dazu dein API-Schlüssel, falls gespeichert | IP-Adresse; Google ruft die Seite selbst ab |

## Schutz

- **RDAP** läuft über den Gatekeeper (`external=True`): DNS über DoH, nur öffentliche Adressen, Verbindung zur geprüften IP, Tempo- und Größenlimit.
- **Safe Browsing und PageSpeed** laufen über `core/thirdparty.py`. Das ist eine bewusste Ausnahme: Der Gatekeeper kann nur GET und hat 15 Sekunden Zeitlimit. Der Client erreicht nur die zwei festen Hosts oben, nur HTTPS auf Port 443, folgt keiner Weiterleitung, ignoriert Umgebungs-Proxys und begrenzt die Antwortgröße. Die Namen löst das System auf, nicht DoH (wie bei der Google-Anmeldung).
- **Die API-Schlüssel** für Safe Browsing und PageSpeed liegen im Windows-Anmeldeinformationsspeicher, nie in einer Datei, nie im Bericht und nie im Protokoll. Auf anderen Systemen nur im Arbeitsspeicher.
- **Ohne Schalter** geht keine Anfrage hinaus, und die zugehörige Prüfung gilt als nicht ausgeführt (`skipped:…_disabled`), nie als bestanden.

## Screenshots (lokal)

Ein eigenes Browser-Skript (`shot_probe.js`) öffnet die Startseite mit denselben Regeln wie der Browser-Lauf (Zielhost auf die geprüfte IP festgelegt, kein HTTP, keine lokalen Adressen, keine Service Worker) und speichert zwei Bilder im Cache-Ordner. Die letzten drei Scans bleiben erhalten. Die Bilder werden nicht auf Geheimnisse geprüft, sie zeigen, was ein Besucher sieht. Der Lauf zählt zum Werkzeugbudget (`core/toolbudget.py`).

## Was geprüft ist

Einmal auf einem GitHub-Rechner gemessen (Linux), noch nicht unter Windows:

- **RDAP:** Die IANA-Liste, die Antwort der Registry für eine `.com`-Domain, die Feldnamen (`events`, `status`) und der Accept-Header des Gatekeepers funktionieren.
- **Safe Browsing:** Der Endpunkt ist erreichbar, ohne Schlüssel antwortet er mit HTTP 403 und einer Fehlerantwort.
- **PageSpeed:** Ohne Schlüssel war das gemeinsame Tageskontingent schon erschöpft (HTTP 429). Praktisch braucht man einen eigenen Schlüssel. Die Prüfung gilt dann als nicht ausgeführt.
- **Screenshots:** `shot_probe.js` hat beide Bilder mit echtem Chromium erzeugt.

## Noch ungeprüft

Das Antwortformat von Safe Browsing und PageSpeed **mit gültigem Schlüssel**. Weicht es ab, gilt die Prüfung als nicht ausgeführt, nie als bestanden.
