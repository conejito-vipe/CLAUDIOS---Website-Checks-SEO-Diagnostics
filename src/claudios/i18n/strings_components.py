"""Zusätzliche UI-Texte für Komponenten und Entfernen. Wird beim Import von claudios.i18n in TEXTS eingemischt."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.components": "Komponenten",
    "cmp.intro": "Externe Prüfwerkzeuge werden nur per HTTPS geladen, gegen eine feste SHA256-Prüfsumme geprüft "
                 "und in deinem Benutzerordner abgelegt. Es sind keine Admin-Rechte nötig.",
    "cmp.col.name": "Komponente", "cmp.col.version": "Version", "cmp.col.size": "Download",
    "cmp.col.status": "Status",
    "cmp.st.installed": "installiert", "cmp.st.missing": "fehlt", "cmp.st.outdated": "veraltet",
    "cmp.st.not_pinned": "nicht gepinnt",
    "cmp.install": "Fehlende installieren / reparieren", "cmp.cancel": "Abbrechen",
    "cmp.uninstall": "Entfernen …",
    "cmp.working": "{name}: {phase} {percent} %",
    "cmp.phase.download": "Download", "cmp.phase.verify": "Prüfsumme", "cmp.phase.extract": "Entpacken",
    "cmp.done": "Fertig: {ok} installiert, {failed} fehlgeschlagen.",
    "cmp.nothing": "Es gibt nichts zu installieren.",
    "cmp.unpinned_hint": "Die Lock-Datei enthält noch keine Prüfsummen. Ungeprüfte Downloads werden nie "
                         "installiert. Führe tools/update_lock.py aus.",
    "cmp.lock_error": "Die Lock-Datei ist unlesbar ({reason}).",
    "cmp.total": "Belegter Speicher der Werkzeuge: {size}",
    "unin.title": "Entfernen",
    "unin.intro": "Wähle, was entfernt werden soll. Berichte und Einstellungen sind nicht vorausgewählt.",
    "unin.item.cache": "Zwischenspeicher", "unin.item.logs": "Protokolle (Programmlog)",
    "unin.item.config": "Einstellungen", "unin.item.reports": "Berichte",
    "unin.warn_dep": "Betroffen: {count} Prüfungen werden nicht mehr ausgeführt. Abhängige Komponenten: {names}.",
    "unin.audit_note": "Das Audit-Protokoll bleibt erhalten, damit die Scan-Grenzen gültig bleiben.",
    "unin.confirm": "Die ausgewählten Teile endgültig entfernen?",
    "unin.done": "Entfernt: {ok}, fehlgeschlagen: {failed}. {details}",
    "unin.hint_failed": "Schließe laufende Prüfwerkzeuge und versuche es erneut.",
    "unin.empty": "Es ist nichts zum Entfernen vorhanden.",
    "unin.ok": "Entfernen", "unin.cancel": "Abbrechen",
})

TEXTS["en"].update({
    "nav.components": "Components",
    "cmp.intro": "External check tools are only downloaded over HTTPS, verified against a fixed SHA256 "
                 "checksum and stored in your user folder. No admin rights are needed.",
    "cmp.col.name": "Component", "cmp.col.version": "Version", "cmp.col.size": "Download",
    "cmp.col.status": "Status",
    "cmp.st.installed": "installed", "cmp.st.missing": "missing", "cmp.st.outdated": "outdated",
    "cmp.st.not_pinned": "not pinned",
    "cmp.install": "Install / repair missing", "cmp.cancel": "Cancel",
    "cmp.uninstall": "Remove …",
    "cmp.working": "{name}: {phase} {percent} %",
    "cmp.phase.download": "download", "cmp.phase.verify": "checksum", "cmp.phase.extract": "extracting",
    "cmp.done": "Done: {ok} installed, {failed} failed.",
    "cmp.nothing": "There is nothing to install.",
    "cmp.unpinned_hint": "The lock file has no checksums yet. Unverified downloads are never installed. "
                         "Run tools/update_lock.py.",
    "cmp.lock_error": "The lock file is unreadable ({reason}).",
    "cmp.total": "Disk space used by the tools: {size}",
    "unin.title": "Remove",
    "unin.intro": "Choose what to remove. Reports and settings are not preselected.",
    "unin.item.cache": "Cache", "unin.item.logs": "Logs (program log)",
    "unin.item.config": "Settings", "unin.item.reports": "Reports",
    "unin.warn_dep": "Affected: {count} checks will no longer run. Dependent components: {names}.",
    "unin.audit_note": "The audit log is kept so that the scan limits stay valid.",
    "unin.confirm": "Remove the selected items permanently?",
    "unin.done": "Removed: {ok}, failed: {failed}. {details}",
    "unin.hint_failed": "Close running check tools and try again.",
    "unin.empty": "There is nothing to remove.",
    "unin.ok": "Remove", "unin.cancel": "Cancel",
})