# FAQ

## Windows warns "Windows protected your PC" (SmartScreen)
Claudios is not code-signed (certificates cost money). Compare the SHA256 checksum shown in the build log with the
downloaded file, and only install files from this repository. / Claudios ist nicht signiert. Vergleiche die
SHA256-Prüfsumme aus dem Build-Protokoll mit der Datei und installiere nur Dateien aus diesem Repository.

## My antivirus flags the program
Programs built with PyInstaller are sometimes flagged by mistake. Build it yourself from the source code if in
doubt. / Mit PyInstaller gebaute Programme werden manchmal fälschlich markiert. Im Zweifel selbst aus dem
Quellcode bauen.

## Why can't I scan a site that has no HTTPS?
By design Claudios opens only HTTPS connections. A site without HTTPS cannot be checked. / Claudios öffnet nur
HTTPS-Verbindungen. Eine Seite ohne HTTPS kann nicht geprüft werden.

## Why is a check shown as "not executed"?
A required tool is missing, a tool failed, or data could not be collected (for example DNS was unreachable). A
check that did not run is never counted as passed. Install tools under "Components". / Ein Werkzeug fehlt, ist
fehlgeschlagen oder Daten waren nicht erreichbar. Nicht ausgeführte Prüfungen zählen nie als bestanden.

## Why does "Components" show "not pinned"?
The lock files carry no checksums yet, and Claudios never installs unverified downloads. Run the lock workflows
in GitHub Actions. / Die Sperrdateien enthalten noch keine Prüfsummen, ungeprüfte Downloads werden nie installiert.
Führe die Sperrdatei-Workflows in GitHub Actions aus.

## Which Python version?
Python 3.12 or 3.13. 3.14 is not tested with the GUI library. / Python 3.12 oder 3.13; 3.14 ist mit der
GUI-Bibliothek nicht geprüft.

## Why can't I install sslyze from the installed program?
The Windows build does not yet ship its own Python runtime, which sslyze's environment needs. It works when you
run Claudios from source. / Der Windows-Build bringt noch keine eigene Python-Laufzeit mit. Aus dem Quellcode
gestartet funktioniert es.

## Can I scan any website?
No. Only your own or explicitly authorised sites. Scanning others without permission can be illegal. Results are
technical indications, not legal advice. / Nein, nur eigene oder ausdrücklich freigegebene Websites.
