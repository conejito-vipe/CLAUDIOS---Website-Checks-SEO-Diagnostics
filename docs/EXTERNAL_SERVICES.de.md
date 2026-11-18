# Externe Dienste in Claudios

English version: [EXTERNAL_SERVICES.md](EXTERNAL_SERVICES.md)

Claudios spricht grundsätzlich nur mit der geprüften Website. Dienste, die Daten an Dritte senden, sind **standardmäßig aus** und lassen sich auf der Seite „Externe Dienste“ einzeln einschalten (jeweils mit Rückfrage). Der Schalter steht in `config/services.json` (nur „Dienst: an/aus“, keine Schlüssel, keine Adressen). Lokale Optionen (Screenshots) stehen in `config/options.json`.

| Dienst | Wohin | Was wird gesendet | Was sieht der Dritte |
|---|---|---|---|
| RDAP (Domainablauf) | `data.iana.org`, dann der RDAP-Server der Endung | die registrierbare Domain | IP-Adresse, User-Agent |
| Safe Browsing | `safebrowsing.googleapis.com` | bis zu 5 Adressen der Website ohne Parameter, dazu dein API-Schlüssel | IP-Adresse, die Adressen |
| PageSpeed Insights | `www.googleapis.com` | die Adresse der Startseite | IP-Adresse; Google ruft die Seite selbst ab |

## Schutz

- **RDAP** läuft über den Gatekeeper (`external=True`): DNS über DoH, nur öffentliche Adressen, Verbindung zur geprüften IP, Tempo- und Größenlimit.
- **Safe Browsing und PageSpeed** laufen über `core/thirdparty.py`. Das ist eine bewusste Ausnahme: Der Gatekeeper kann nur GET und hat 15 Sekunden Zeitlimit. Der Client erreicht nur die zwei festen Hosts oben, nur HTTPS auf Port 443, folgt keiner Weiterleitung, ignoriert Umgebungs-Proxys und begrenzt die Antwortgröße. Die Namen löst das System auf, nicht DoH (wie bei der Google-Anmeldung).
- **Der API-Schlüssel** für Safe Browsing liegt im Windows-Anmeldeinformationsspeicher, nie in einer Datei, nie im Bericht und nie im Protokoll. Auf anderen Systemen nur im Arbeitsspeicher.
- **Ohne Schalter** geht keine Anfrage hinaus, und die zugehörige Prüfung gilt als nicht ausgeführt (`skipped:…_disabled`), nie als bestanden.

## Screenshots (lokal)

Ein eigenes Browser-Skript (`shot_probe.js`) öffnet die Startseite mit denselben Regeln wie der Browser-Lauf (Zielhost auf die geprüfte IP festgelegt, kein HTTP, keine lokalen Adressen, keine Service Worker) und speichert zwei Bilder im Cache-Ordner. Die letzten drei Scans bleiben erhalten. Die Bilder werden nicht auf Geheimnisse geprüft, sie zeigen, was ein Besucher sieht. Der Lauf zählt zum Werkzeugbudget (`core/toolbudget.py`).

## Ungeprüft

Format der IANA-Liste und der RDAP-Antworten, der Safe-Browsing-Endpunkt (v4 `threatMatches:find` mit `?key=`), die Antwortfelder von PageSpeed (`lighthouseResult`, `loadingExperience`) und das Verhalten von `shot_probe.js` mit einem echten Chromium stammen aus dem Gedächtnis. Bei Abweichungen gilt die Prüfung als nicht ausgeführt, nie als bestanden.
