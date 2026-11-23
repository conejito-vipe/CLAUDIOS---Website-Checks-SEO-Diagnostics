"""UI-Texte der Update-Funktion."""
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
