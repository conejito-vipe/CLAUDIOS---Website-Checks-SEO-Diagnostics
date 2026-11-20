# Firefox, WebKit und die Python-Laufzeit

English version: [ENGINES_AND_RUNTIME.md](ENGINES_AND_RUNTIME.md)

## Browser-Vergleich (Firefox und WebKit)

- **Wann:** nur im Profil Tief und nur mit der Komponente „Firefox und WebKit“ (Seite Komponenten).
- **Was:** höchstens 3 Seiten, ein Lauf von `engine_probe.js`. Er zählt zum Werkzeugbudget (Browser-Läufe je Scan: 4).
- **Regeln:** wie beim Chromium-Lauf: kein HTTP, keine lokalen Adressen, keine Service Worker, Zertifikatsfehler werden nie ignoriert.
- **Grenze:** Der Zielhost ist hier **nicht** an die geprüfte IP festgelegt (bei Chromium geschieht das mit `--host-resolver-rules`). CLAUDIOS prüft die Auflösung vor und nach dem Lauf (`core/rebind.py`) und danach die beobachteten Fremd-Hosts (`core/foreign.py`, Prüfung `BRW-FRN-001`). Ein Wechsel mitten im Lauf wird erkannt, nicht verhindert.
- **Downloads:** Playwright lädt Firefox und WebKit von seinem eigenen Server über HTTPS. CLAUDIOS pinnt diese Dateien nicht (wie bei Chromium).

## Python-Laufzeit für sslyze (nur im gebauten Windows-Programm)

- Das Programm hat kein eigenes Python. Deshalb gibt es zwei Komponenten, die nur im gebauten Programm erscheinen: `python-runtime` (Python embeddable) und `pip-wheel` (pip). Beide sind in `components/runtime-lock.json` mit SHA256 gepinnt. Die Datei erzeugt der Workflow „Laufzeit-Sperrdatei erzeugen“.
- sslyze wird in eine Kopie der Laufzeit installiert (`pip --require-hashes --no-deps`, nur aus `pip-sslyze.json`).
- **Reihenfolge:** erst den Workflow „Laufzeit-Sperrdatei erzeugen“ starten, dann den Windows-Build.
- **Ungeprüft:** ob der Bau von sslyze aus dem Quellarchiv in der eingebetteten Laufzeit gelingt. Bis dahin gilt die Prüfung TLS-PRO-001 als nicht ausgeführt, nie als bestanden.
