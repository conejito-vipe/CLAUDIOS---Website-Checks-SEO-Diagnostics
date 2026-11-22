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
