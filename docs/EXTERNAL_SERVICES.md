# Externe Dienste in Claudios

Claudios spricht grundsätzlich nur mit der geprüften Website. Dienste, die Daten an Dritte senden, sind **standardmäßig
aus** und lassen sich auf der Seite „Externe Dienste“ einzeln einschalten. Der Schalter wird in `config/services.json`
gespeichert (nur „Dienst: an/aus“, keine Schlüssel, keine Adressen).

## RDAP (Domainablauf)

| | |
|---|---|
| Wann | nur mit Schalter, bei jedem Scan einer Domain (nicht bei Localhost) |
| Wohin | `data.iana.org` (Liste der RDAP-Server), danach der für die Endung zuständige RDAP-Server |
| Was wird gesendet | die registrierbare Domain, zum Beispiel `beispiel.de`. Nie eine Unterseite, nie Inhalte des Berichts |
| Was sehen die Server | die IP-Adresse des Nutzers und den Programmnamen im User-Agent |
| Schutz | beide Anfragen laufen über den Gatekeeper (`external=True`): DNS über DoH, nur öffentliche Adressen, Verbindung zur geprüften IP, Tempo- und Datenlimit |
| Gespeichert | nur Ablaufdatum und Status-Wörter im Scan-Ergebnis |

Ungeprüft: Format der IANA-Liste und der RDAP-Antworten (aus dem Gedächtnis), und ob jeder Server auf den
Standard-Accept-Header JSON liefert. Wenn nicht, gilt die Prüfung als nicht ausgeführt (`skipped:rdap_unreadable`),
nie als bestanden.
