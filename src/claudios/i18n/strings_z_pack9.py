"""UI-Texte von Paket 9. Der Dateiname sortiert hinter strings_ui2, damit diese Texte dessen Fassung überschreiben."""
from __future__ import annotations

from ..core.limits import LIMITS
from .strings import TEXTS

HOURS = LIMITS.audit_tamper_lock_seconds // 3600

TEXTS["de"].update({
    "cmp.col.download": "Download", "cmp.col.disk": "Belegt", "cmp.approx": "ca. {size}",
    "cmp.total2": "Belegter Speicher auf der Festplatte (entpackt): {size}. Das ist deutlich mehr als der Download, "
                  "weil die Pakete entpackt werden (Chromium, Java und Node.js sind entpackt groß).",
    "app.running": "CLAUDIOS läuft bereits. Bitte nutze das schon geöffnete Fenster. Zwei gleichzeitig laufende "
                   "Programme würden dieselben Werkzeuge einrichten und sich gegenseitig blockieren.",
    "splash.audit_warn": "Das Scan-Protokoll (Ordner logs, Datei audit.jsonl) wurde verändert, ersetzt oder gelöscht "
                         "oder ist beschädigt. Als Missbrauchsschutz können neue Scans deshalb für bis zu "
                         f"{HOURS} Stunden gesperrt sein. Das passiert auch, wenn die Datei von Hand bearbeitet oder durch "
                         "eine Kopie ersetzt wurde oder wenn der Ordner CLAUDIOS gelöscht wurde, während der "
                         "Kontrollwert im Windows-Anmeldeinformationsspeicher erhalten blieb. Kopiere die Datei nur "
                         "zur Sicherung und lass das Original an seinem Platz.",
    "app.uninstall.confirm": "CLAUDIOS wird mit allen eingerichteten Werkzeugen (Komponenten), dem Cache, den "
                             "Einstellungen, Berichten, dem Verlauf und gespeicherten API-Schlüsseln entfernt. Danach "
                             "startet die Deinstallation des Programms. Das Scan-Protokoll mit den Tageslimits bleibt "
                             "bewusst erhalten, damit sich die Limits durch eine Neuinstallation nicht zurücksetzen. "
                             "Ändere, ersetze oder lösche die Datei audit.jsonl im Ordner logs nicht von Hand und "
                             f"kopiere sie nur zur Sicherung: sonst sperrt der Missbrauchsschutz neue Scans für {HOURS} "
                             "Stunden. Fortfahren?",
})
TEXTS["en"].update({
    "cmp.col.download": "Download", "cmp.col.disk": "Used", "cmp.approx": "approx. {size}",
    "cmp.total2": "Disk space used (unpacked): {size}. This is clearly more than the download because the packages "
                  "are unpacked (Chromium, Java and Node.js are large when unpacked).",
    "app.running": "CLAUDIOS is already running. Please use the window that is already open. Two programs running at "
                   "the same time would set up the same tools and block each other.",
    "splash.audit_warn": "The scan log (folder logs, file audit.jsonl) was modified, replaced or deleted, or it is "
                         f"damaged. As abuse protection, new scans can therefore be blocked for up to {HOURS} hours. "
                         "This also happens if the file was edited by hand or replaced by a copy, or if the CLAUDIOS "
                         "folder was deleted while the control value in the Windows Credential Manager remained. Copy "
                         "the file only as a backup and leave the original in place.",
    "app.uninstall.confirm": "CLAUDIOS is removed together with all installed tools (components), the cache, settings, "
                             "reports, history and stored API keys. Then the uninstallation of the program starts. "
                             "The scan log with the daily limits is deliberately kept so that a reinstallation does "
                             "not reset the limits. Do not edit, replace or delete the file audit.jsonl in the logs "
                             f"folder by hand and copy it only as a backup: otherwise the abuse protection blocks new "
                             f"scans for {HOURS} hours. Continue?",
})
