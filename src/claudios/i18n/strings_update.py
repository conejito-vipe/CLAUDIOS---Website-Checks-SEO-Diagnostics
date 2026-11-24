"""UI-Texte der Update-Funktion, der Einstellungen, der Hilfe, des Verlaufs und der Befund-Hinweise."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "upd.title": "Update verfügbar",
    "upd.text": "CLAUDIOS {version} ist verfügbar (installiert: {current}). Jetzt herunterladen und installieren? Die "
                "Prüfsumme der Datei wird vor dem Start des Installers kontrolliert. CLAUDIOS wird dafür beendet und "
                "danach neu gestartet.",
    "upd.never": "Nicht mehr automatisch suchen",
    "upd.downloading": "Update {version} wird geladen … {percent} %",
    "upd.start_failed": "Der Installer konnte nicht gestartet werden. Die Datei liegt hier: {path}",
})
TEXTS["en"].update({
    "upd.title": "Update available",
    "upd.text": "CLAUDIOS {version} is available (installed: {current}). Download and install it now? The checksum of "
                "the file is verified before the installer starts. CLAUDIOS closes for this and starts again afterwards.",
    "upd.never": "Do not search automatically",
    "upd.downloading": "Downloading update {version} … {percent} %",
    "upd.start_failed": "The installer could not be started. The file is here: {path}",
})

TEXTS["de"].update({
    "settings.updates": "Beim Start nach einer neuen Version suchen",
    "settings.updates_note": "Dazu fragt das installierte Programm beim Start bei GitHub nach der neuesten Version. "
                             "Ausgeschaltet findet diese Anfrage nicht statt. Die Änderung gilt ab dem nächsten Start.",
})
TEXTS["en"].update({
    "settings.updates": "Check for a new version at startup",
    "settings.updates_note": "For this, the installed program asks GitHub for the latest version at startup. "
                             "When switched off, this request is not made. The change applies from the next start.",
})

TEXTS["de"].update({
    "nav.help": "Hilfe",
    "boot.firstrun": "Hinweis: Beim ersten Start werden die Prüfwerkzeuge geladen und eingerichtet. Das kann "
                     "4 bis 5 Minuten dauern.",
})
TEXTS["en"].update({
    "nav.help": "Help",
    "boot.firstrun": "Note: on the first start the check tools are downloaded and set up. This can take "
                     "4 to 5 minutes.",
})

TEXTS["de"].update({
    "hv.title": "Verlauf: gescannte Websites",
    "hv.col.when": "Website / Tag / Uhrzeit",
    "hv.col.score": "Wertung",
    "hv.col.status": "Status",
    "hv.scans": "{count} Scans",
    "hv.pick": "Wähle einen Scan, um seine Befunde zu sehen. Der Verlauf speichert nur Zusammenfassungen, keine "
               "Adressen und keine Belege.",
    "hv.empty": "Noch keine gespeicherten Scans. Der Verlauf füllt sich nach jedem Scan, solange der Schalter oben "
                "eingeschaltet ist.",
    "hv.head": "{host} · {day} {time} · Status: {status} · Wertung {score}/100",
    "hv.none": "Dieser Scan hatte keine Befunde.",
    "detail.nocode_result": "Kein Codefenster: Der Scan-Stand mit dem Quelltext liegt nicht mehr vor (zum Beispiel nach "
                            "einem Neustart).",
    "detail.nocode_source": "Kein Codefenster: Zu dieser Adresse ist im Scan kein gespeicherter Quelltext vorhanden.",
    "detail.nocode_range": "Kein Codefenster: Die Zeile aus dem Beleg liegt außerhalb des gespeicherten Textes.",
})
TEXTS["en"].update({
    "hv.title": "History: scanned websites",
    "hv.col.when": "Website / day / time",
    "hv.col.score": "Score",
    "hv.col.status": "Status",
    "hv.scans": "{count} scans",
    "hv.pick": "Select a scan to see its findings. The history stores only summaries, no addresses and no evidence.",
    "hv.empty": "No saved scans yet. The history fills after every scan as long as the switch above is on.",
    "hv.head": "{host} · {day} {time} · Status: {status} · Score {score}/100",
    "hv.none": "This scan had no findings.",
    "detail.nocode_result": "No code window: the scan data with the source code is no longer available (for example "
                            "after a restart).",
    "detail.nocode_source": "No code window: no stored source code exists in the scan for this address.",
    "detail.nocode_range": "No code window: the line from the evidence lies outside the stored text.",
})
