# FAQ

English version: [FAQ.md](FAQ.md)

## Windows warnt „Der Computer wurde durch Windows geschützt“ (SmartScreen)
Claudios ist nicht signiert (Zertifikate kosten Geld). Vergleiche die SHA256-Prüfsumme aus dem Build-Protokoll mit der Datei und installiere nur Dateien aus diesem Repository.

## Mein Virenscanner meldet das Programm
Mit PyInstaller gebaute Programme werden manchmal fälschlich markiert. Im Zweifel selbst aus dem Quellcode bauen.

## Warum kann ich keine Seite ohne HTTPS prüfen?
Claudios öffnet nur HTTPS-Verbindungen. Eine Seite ohne HTTPS kann nicht geprüft werden.

## Warum steht eine Prüfung als „nicht ausgeführt“?
Ein Werkzeug fehlt, ein Werkzeug ist fehlgeschlagen, der Schalter für einen Online-Dienst ist aus, oder Daten waren nicht erreichbar (zum Beispiel DNS). Nicht ausgeführte Prüfungen zählen nie als bestanden. Installiere Werkzeuge unter „Komponenten“; die Seite „Befunde“ listet jede nicht ausgeführte Prüfung mit Grund.

## Warum zeigt „Komponenten“ „nicht gepinnt“?
Die Sperrdateien enthalten noch keine Prüfsummen, und Claudios installiert nie ungeprüfte Downloads. Führe die Sperrdatei-Workflows in GitHub Actions aus („Werkzeug-Prüfsummen eintragen“, die Workflows für npm, pip und Playwright und „Laufzeit-Sperrdatei erzeugen“).

## Welche Python-Version?
Python 3.12 oder 3.13; 3.14 ist mit der GUI-Bibliothek nicht geprüft.

## Kann ich sslyze im installierten Programm installieren?
Das gebaute Programm hat kein eigenes Python. Es lädt eine feste Python-Laufzeit (embeddable, Prüfsumme in `components/runtime-lock.json`) und installiert sslyze in eine Kopie davon. Das ist auf echten Rechnern noch nicht geprüft. Bis es funktioniert, gilt die TLS-Prüfung als nicht ausgeführt.

## Was ist Stufe 2?
Stufe 2 braucht eine Google-Anmeldung und Inhaber- oder Vollzugriff auf die Domain in der Search Console. Sie erlaubt aktive Prüfungen, bis zu 100 Seiten und Search-Console-Daten. Siehe [docs/GOOGLE_SETUP.de.md](docs/GOOGLE_SETUP.de.md).

## Sendet Claudios Daten an Dritte?
Nur an die geprüfte Website, es sei denn, du schaltest auf der Seite „Externe Dienste“ einen optionalen Dienst ein (Domainablauf, Safe Browsing, PageSpeed). Alle sind standardmäßig aus und fragen vor dem Einschalten nach. Siehe [docs/EXTERNAL_SERVICES.de.md](docs/EXTERNAL_SERVICES.de.md).

## Werden meine Scans gespeichert?
Nein, außer du schaltest den Verlauf auf der Seite „Export & Verlauf“ ein (eine kurze Zusammenfassung je Scan, nie Adressen oder Seiteninhalte, höchstens 20 je Domain). Screenshots entstehen nur, wenn du die Option einschaltest, und bleiben auf deinem Rechner.

## Darf ich jede Website prüfen?
Nein, nur eigene oder ausdrücklich freigegebene Websites. Fremde Seiten ohne Erlaubnis zu prüfen kann strafbar sein. Ergebnisse sind technische Indizien, keine Rechtsberatung.
