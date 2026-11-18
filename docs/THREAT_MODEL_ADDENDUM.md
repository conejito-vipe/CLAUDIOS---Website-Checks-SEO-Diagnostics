# Ergänzung zum Bedrohungsmodell (Stand: Pakete 6f bis 6n)

`THREAT_MODEL.md` bleibt unverändert. Diese Datei hält fest, was seit 6f dazugekommen ist. Zu den Schutzschichten siehe
`docs/ABUSE_PROTECTION.md`, zu Diensten bei Dritten `docs/EXTERNAL_SERVICES.md`.

## Restrisiken
- **Fremdserver werden erkannt, nicht verhindert.** Chromium und ZAP lösen die Namen von Fremdservern selbst auf. Zeigt ein
  Name auf eine nicht öffentliche Adresse, ist der Zugriff schon geschehen. Claudios löst jeden beobachteten Host danach
  erneut per DoH auf, verwirft seine Daten und meldet ihn (`BRW-FRN-001`).
- **Beim ZAP-Lauf ist der Zielhost nicht an die geprüfte IP gebunden.** Dort gilt nur die Prüfung der Auflösung vor und
  nach dem Lauf (`core/rebind.py`).
- **Der Kontrollwert des Scan-Protokolls ist Reibung, kein Schutz.** Wer Protokoll und Kontrollwert löscht, sieht aus wie
  eine Neuinstallation.
- **Safe Browsing und PageSpeed lösen Namen über das System auf**, nicht über DoH. Die Ziele sind zwei feste Google-Hosts,
  ohne Weiterleitung und mit Größenlimit.
- **Screenshots zeigen Seiteninhalt.** Sie bleiben lokal und werden nur auf Wunsch als ZIP gespeichert, aber nicht auf
  Geheimnisse geprüft.
- **PageSpeed lässt Google die Seite abrufen.** Das ist ein normaler Seitenaufruf durch einen Dritten, nur auf ausdrücklichen
  Wunsch.

## Nicht gelöst
- Windows-Build, echte Google-Anmeldung und das Schreiben des Kontrollwerts in den Anmeldeinformationsspeicher sind
  ungetestet.
