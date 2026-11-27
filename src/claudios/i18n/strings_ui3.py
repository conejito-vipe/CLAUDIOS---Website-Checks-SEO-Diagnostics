"""Texte für Maximieren, Experteneinstellungen im eigenen Fenster und die wählbare Deinstallation."""
from . import strings

strings.TEXTS["de"].update({
    "win.maximize": "Maximieren", "win.restore": "Verkleinern",
    "expert.open": "Experteneinstellungen …", "expert.title": "Experteneinstellungen", "expert.ok": "Speichern",
    "expert.keys_hint": "Die Schlüssel verwaltest du unter „Einstellungen“ (Zahnrad oben). Dieses Fenster schließt sich dann, ungespeicherte Änderungen entfallen.",
    "uni.title": "CLAUDIOS deinstallieren",
    "uni.intro": "Hier siehst du alles, was CLAUDIOS auf diesem Computer angelegt hat. Angehakte Einträge werden "
                 "gelöscht. Deine Daten (Einstellungen, Berichte, Verlauf, Schlüssel) sind nicht vorgewählt.",
    "uni.personal": "deine Daten", "uni.size": "{size}",
    "uni.item.tool": "Prüfwerkzeug: {name}", "uni.item.cache": "Zwischenspeicher", "uni.item.logs": "Protokolldateien",
    "uni.item.config": "Einstellungen", "uni.item.reports": "Berichte", "uni.item.history": "Verlauf der Scans",
    "uni.item.keys": "Gespeicherte API-Schlüssel", "uni.item.program": "Programm (Deinstallation starten)",
    "uni.why.tool": "Wird beim nächsten Start nach Bedarf neu geladen.",
    "uni.why.cache": "Zwischengespeicherte Daten, können jederzeit neu entstehen.",
    "uni.why.logs": "Fehler- und Ablaufprotokolle.",
    "uni.why.config": "Deine Einstellungen und Schalter.", "uni.why.reports": "Von dir gespeicherte Berichte.",
    "uni.why.history": "Zusammenfassungen früherer Scans.", "uni.why.keys": "Im Anmelde-Speicher des Systems abgelegt.",
    "uni.why.program": "Entfernt die Programmdateien und startet danach den Deinstaller.",
    "uni.confirm": "Ich habe die Liste gelesen und möchte die angehakten Einträge unwiderruflich löschen.",
    "uni.go": "Jetzt deinstallieren", "uni.cancel": "Abbrechen", "uni.none": "Nichts ausgewählt.",
    "uni.kept": "Das Scan-Protokoll bleibt bewusst erhalten, damit Tageslimits und Sperren nach einer Neuinstallation "
                "weiter gelten.",
})
strings.TEXTS["en"].update({
    "win.maximize": "Maximize", "win.restore": "Restore",
    "expert.open": "Expert settings …", "expert.title": "Expert settings", "expert.ok": "Save",
    "expert.keys_hint": "Manage keys under “Settings” (gear at the top). This window closes then, unsaved changes are dropped.",
    "uni.title": "Uninstall CLAUDIOS",
    "uni.intro": "Here is everything CLAUDIOS created on this computer. Ticked items will be deleted. Your data "
                 "(settings, reports, history, keys) is not preselected.",
    "uni.personal": "your data", "uni.size": "{size}",
    "uni.item.tool": "Check tool: {name}", "uni.item.cache": "Cache", "uni.item.logs": "Log files",
    "uni.item.config": "Settings", "uni.item.reports": "Reports", "uni.item.history": "Scan history",
    "uni.item.keys": "Stored API keys", "uni.item.program": "Program (start the uninstaller)",
    "uni.why.tool": "Is downloaded again on demand at the next start.",
    "uni.why.cache": "Cached data that can be recreated at any time.",
    "uni.why.logs": "Error and activity logs.",
    "uni.why.config": "Your settings and switches.", "uni.why.reports": "Reports you saved.",
    "uni.why.history": "Summaries of earlier scans.", "uni.why.keys": "Kept in the system credential store.",
    "uni.why.program": "Removes the program files and then starts the uninstaller.",
    "uni.confirm": "I have read the list and want to delete the ticked items permanently.",
    "uni.go": "Uninstall now", "uni.cancel": "Cancel", "uni.none": "Nothing selected.",
    "uni.kept": "The scan log is deliberately kept so daily limits and locks still apply after a reinstall.",
})
strings.TEXTS["de"]["svc.back"] = "← Zurück zum Scan"
strings.TEXTS["en"]["svc.back"] = "← Back to the scan"
