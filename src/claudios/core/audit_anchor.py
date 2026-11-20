"""Kontrollwert gegen das Löschen des Audit-Logs: Anzahl der Einträge und letzter Hash liegen im
Windows-Anmeldeinformationsspeicher (nie in einer Datei). Stimmt das Protokoll nicht mehr dazu, wird es beiseitegelegt,
ein neues beginnt mit dem Eintrag "tamper", und Scans sind für die Sperrzeit (3 Stunden) gesperrt.
Grenze: Wer Protokoll und Kontrollwert löscht, sieht aus wie eine Neuinstallation (Reibung, kein Schutz)."""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

if TYPE_CHECKING:
    from .audit_log import AuditLog

NAME = "Claudios audit anchor"


class Anchor:
    def __init__(self, store, name: str = NAME) -> None:
        self.store, self.name = store, name

    def load(self) -> tuple[int, str] | None:
        raw = self.store.read(self.name)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            count, last_hash = int(data["n"]), str(data["h"])
        except (ValueError, KeyError, TypeError):
            return None
        return (count, last_hash) if count >= 1 and len(last_hash) == 64 else None

    def save(self, count: int, last_hash: str, *, force: bool = False) -> None:
        """Der Kontrollwert darf nur wachsen, außer force=True (Neubeginn nach einer Veränderung)."""
        if not force:
            current = self.load()
            if current is not None and count < current[0]:
                return
        self.store.write(self.name, json.dumps({"n": count, "h": last_hash}, separators=(",", ":")))

    @staticmethod
    def _inspect(log: AuditLog, state: tuple[int, str] | None) -> tuple[str | None, list[dict]]:
        try:
            recs = log.records()
            intact = log.verify()
        except (ValueError, KeyError, TypeError):
            return "unreadable", []
        if not intact:
            return "chain", recs
        if state is not None:
            count, last_hash = state
            if len(recs) < count:
                return "shorter", recs
            if recs[count - 1]["hash"] != last_hash:
                return "replaced", recs
        return None, recs

    def _restart(self, log: AuditLog, reason: str) -> None:
        path = log.path
        if path.exists():
            try:
                path.replace(path.with_name(path.name + ".tampered"))
            except OSError:
                raise ClaudiosError(E.FS_ERROR, reason="audit log") from None
        log.append("tamper", reason=reason)
        recs = log.records()
        self.save(len(recs), recs[-1]["hash"], force=True)

    def check(self, log: AuditLog, now: float | None = None) -> None:
        """Wirft AUDIT_TAMPERED, solange eine Veränderung innerhalb der Sperrzeit zurückliegt."""
        now = time.time() if now is None else now
        state = self.load()
        reason, recs = self._inspect(log, state)
        if reason:
            self._restart(log, reason)
        elif recs and state != (len(recs), recs[-1]["hash"]):
            self.save(len(recs), recs[-1]["hash"])
        if log.count("tamper", LIMITS.audit_tamper_lock_seconds, now=now):
            raise ClaudiosError(E.AUDIT_TAMPERED, hours=int(LIMITS.audit_tamper_lock_seconds // 3600))


def default_anchor() -> Anchor | None:
    """Nur mit dauerhaftem Speicher (Windows). Im Arbeitsspeicher wäre ein Kontrollwert wertlos."""
    from ..gsc.credstore import get_store

    store = get_store()
    return Anchor(store) if getattr(store, "persistent", False) else None
