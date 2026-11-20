# Missbrauchsschutz in CLAUDIOS

English version: [ABUSE_PROTECTION.md](ABUSE_PROTECTION.md)

Dieses Dokument beschreibt, wie CLAUDIOS verhindert, dass es gegen fremde Websites oder das eigene Netz missbraucht wird, und wo diese Schutzmaßnahmen enden. Es ergänzt [THREAT_MODEL.de.md](../THREAT_MODEL.de.md).

## Schichten

| Schicht | Wirkung | Datei |
|---|---|---|
| Eingabe | Eine Domain, nur HTTPS, Port 443, strenge Hostnamen-Regeln, keine lokalen Endungen, keine IP-Adressen, Punycode. Ein im Scan-Feld getipptes `http://` wird zu `https://`, sonst wird nichts gelockert | `core/guard.py`, `ui/urlinput.py` |
| Selbstauskunft / Stufe 2 | Stufe 1 nur mit Haken. Stufe 2 nur mit Beleg der Live-Prüfung der Search-Console-Properties: gilt für einen Host und eine Property, 15 Minuten, einmal | `core/proof.py`, `gsc/session.py` |
| Kontingent | Abkühlzeit 30 s (als Countdown sichtbar), 5 Scans pro Stunde, 5 (Stufe 1) oder 12 (Stufe 2) pro Domain und Tag | `core/quota.py`, `core/limits.py` |
| Scan-Protokoll | Hash-Kette plus Kontrollwert im Windows-Anmeldeinformationsspeicher. Ein gelöschtes oder verändertes Protokoll sperrt Scans 3 Stunden | `core/audit_log.py`, `core/audit_anchor.py` |
| Gatekeeper | Jeder eigene Zugriff läuft hier durch: DNS nur über DoH, alle Adressen müssen öffentlich sein, Verbindung zur geprüften IP, Tempo- und Größenlimits | `core/net.py` |
| Werkzeuge | Browser, ZAP und sslyze: Gesamtbudget 1.800 s, 15 s Pause zwischen Läufen, höchstens 4 Läufe je Art und Scan | `core/toolbudget.py`, `core/toolrunner.py` |
| DNS-Rebinding | Die Auflösung wird vor und nach dem ZAP-Lauf und dem Firefox/WebKit-Lauf erneut geprüft. Der Chromium-Lauf legt den Zielhost auf die geprüfte IP fest. Eingebettete IPv4-Adressen in NAT64- und 6to4-Adressen werden nach der IPv4-Adresse beurteilt | `core/rebind.py`, `core/guard.py`, `checks/_browser.py` |
| Fremd-Hosts | Hosts, die Browser und ZAP selbst aufgelöst haben, werden danach geprüft. Zeigt einer auf eine nicht öffentliche Adresse, werden seine Daten verworfen und er wird gemeldet (`BRW-FRN-001`) | `core/foreign.py` |
| Optionale Dienste | Standardmäßig aus, Einschalten nur nach Rückfrage, vor jedem Scan erneut gefragt. Siehe [EXTERNAL_SERVICES.de.md](EXTERNAL_SERVICES.de.md) | `core/services.py`, `core/thirdparty.py`, `ui/expert_box.py` |

## Grenzen (Restrisiken)

- **Beleg und Kontrollwert sind Reibung, kein Schutz vor einem Entwickler.** Wer den Quellcode ändert oder Protokoll und Kontrollwert löscht, umgeht sie. Eine Neuinstallation sieht genauso aus.
- **Fremd-Hosts werden erkannt, nicht verhindert.** Chromium, Firefox, WebKit und ZAP lösen ihre Namen selbst auf. Ein Wechsel mitten im Lauf wird nur danach erkannt; der Zugriff ist dann schon geschehen.
- **Im ZAP-Lauf und im Firefox/WebKit-Lauf ist der Zielhost nicht an die geprüfte IP gebunden.** Dort gilt nur die Prüfung vor und nach dem Lauf.
- **Das Budget erfasst nicht den ZAP-Daemon selbst**, nur das Browser-Skript durch ZAP.
- **Ein abgelehnter Werkzeuglauf zeigt sich als `skipped:tool_failed`.** Der Grund (`budget`) steht nur im Log.
- **Ungeprüft unter Windows:** das Schreiben des Kontrollwerts in den Anmeldeinformationsspeicher. Die ZAP-Schnittstelle `core/view/hosts` ist unter Linux bestätigt.

## Wie es geprüft wird

Die Tests `test_abuse_protection.py`, `test_audit_anchor.py`, `test_rebinding.py`, `test_foreign_hosts.py` und `test_tool_budget.py` decken die Schichten ab. Eine Freigabeliste in einem Test verhindert, dass unbemerkt neue aktive Prüfungen oder Probes der Stufe 2 entstehen.

## Das Scan-Protokoll nicht von Hand anfassen

Das Scan-Protokoll (`audit.jsonl` im Ordner `logs`) ist mit Hashes verkettet und hat einen Kontrollwert im Windows-Anmeldeinformationsspeicher. Wird die Datei bearbeitet, durch eine Kopie ersetzt, verschoben oder gelöscht (oder wird der Datenordner CLAUDIOS gelöscht, während der Kontrollwert bleibt), wertet das Programm das als Manipulation und sperrt neue Scans für 3 Stunden. Kopiere die Datei nur zur Sicherung und lass das Original an seinem Platz. Die Deinstallieren-Funktion behält das Protokoll absichtlich.
