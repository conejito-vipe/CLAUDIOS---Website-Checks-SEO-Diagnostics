"""UI-Texte: Einrichtung beim Start, Deinstallation, abgebrochene Scans."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "boot.intro": "Fehlende Prüfwerkzeuge werden geladen und per Prüfsumme geprüft. Das kann beim ersten Start einige "
                  "Minuten dauern.",
    "boot.status": "Komponenten werden eingerichtet ({done} von {total} fertig): {active}",
    "boot.skip": "Programm starten, Einrichtung später fortsetzen",
    "boot.failed": "{count} Komponente(n) konnten nicht eingerichtet werden:\n\n{details}\n\nDie zugehörigen Prüfungen "
                   "gelten als nicht ausgeführt. Du kannst es auf der Seite Komponenten erneut versuchen.",
    "app.uninstall": "CLAUDIOS deinstallieren",
    "app.uninstall.confirm": "CLAUDIOS wird mit allen eingerichteten Werkzeugen (Komponenten), dem Cache, den "
                             "Einstellungen, Berichten, dem Verlauf und gespeicherten API-Schlüsseln entfernt. Danach "
                             "startet die Deinstallation des Programms. Das Scan-Protokoll mit den Tageslimits bleibt "
                             "bewusst erhalten, damit sich die Limits durch eine Neuinstallation nicht zurücksetzen. "
                             "Fortfahren?",
    "app.uninstall.partial": "Einige Teile konnten nicht entfernt werden: {items}. Lösche sie bei Bedarf von Hand im "
                             "Ordner {folder}.",
    "app.uninstall.manual.mac": "Die Werkzeuge und Daten wurden entfernt. Das Programm selbst entfernst du, indem du "
                                "CLAUDIOS.app aus dem Ordner Programme in den Papierkorb legst.",
    "app.uninstall.manual": "Die Werkzeuge und Daten wurden entfernt. Das Programm selbst deinstallierst du über die "
                            "Windows-Einstellungen unter Apps.",
    "res.summary_aborted": "{target} · Status: {status} · keine Gesamtwertung · {pages} Seiten · {requests} Anfragen "
                           "· {size}",
})
TEXTS["en"].update({
    "boot.intro": "Missing check tools are downloaded and verified by checksum. The first start can take a few minutes.",
    "boot.status": "Setting up components ({done} of {total} done): {active}",
    "boot.skip": "Start the program, finish setup later",
    "boot.failed": "{count} component(s) could not be set up:\n\n{details}\n\nThe matching checks count as not "
                   "executed. You can try again on the Components page.",
    "app.uninstall": "Uninstall CLAUDIOS",
    "app.uninstall.confirm": "CLAUDIOS is removed together with all installed tools (components), the cache, settings, "
                             "reports, history and stored API keys. Then the uninstallation of the program starts. "
                             "The scan log with the daily limits is deliberately kept so that a reinstallation does "
                             "not reset the limits. Continue?",
    "app.uninstall.partial": "Some parts could not be removed: {items}. Delete them by hand in the folder "
                             "{folder} if you like.",
    "app.uninstall.manual.mac": "The tools and data were removed. Remove the program itself by moving CLAUDIOS.app "
                                "from the Applications folder to the Trash.",
    "app.uninstall.manual": "The tools and data were removed. Uninstall the program itself in the Windows settings "
                            "under Apps.",
    "res.summary_aborted": "{target} · Status: {status} · no overall score · {pages} pages · {requests} requests "
                           "· {size}",
})
