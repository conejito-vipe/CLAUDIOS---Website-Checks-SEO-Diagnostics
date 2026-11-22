"""Audit-Log mit Hash-Kette. Nur Zeit, Ereignis, Domain, Stufe, Profil. Keine personenbezogenen Daten.
Optional mit Kontrollwert (core/audit_anchor.py) gegen das Löschen der Datei. Das Programm schaltet ihn in app.py
für alle neuen Protokolle ein (use_default_anchor); Tests lassen ihn aus."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audit_anchor import Anchor

_ZERO = "0" * 64
_DEFAULT: dict[str, Callable[[], Anchor | None] | None] = {"factory": None}


def use_default_anchor(factory: Callable[[], Anchor | None] | None) -> None:
    """Alle danach erzeugten AuditLog-Objekte ohne eigenen Kontrollwert bekommen den der Fabrik (None = keiner)."""
    _DEFAULT["factory"] = factory


def _digest(prev: str, rec: dict) -> str:
    body = json.dumps({k: rec[k] for k in ("t", "event", "data")}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256((prev + body).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path | str, anchor: Anchor | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        factory = _DEFAULT["factory"]
        self.anchor = anchor if anchor is not None or factory is None else factory()
        self._lock = threading.Lock()

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return self._parse(self.path.read_text("utf-8-sig"))

    @staticmethod
    def _parse(text: str) -> list[dict]:
        """Eine letzte Zeile ohne Zeilenende, die sich nicht lesen lässt, ist halb geschrieben (Abbruch) und zählt nicht."""
        lines = text.split("\n")
        if lines and lines[-1].strip():
            try:
                json.loads(lines[-1])
            except ValueError:
                lines.pop()
        return [json.loads(x) for x in lines if x.strip()]

    def _heal(self) -> None:
        """Entfernt einen halb geschriebenen letzten Eintrag, bevor neu angehängt wird."""
        try:
            raw = self.path.read_bytes()
        except OSError:
            return
        if not raw or raw.endswith(b"\n"):
            return
        cut = raw.rfind(b"\n") + 1
        try:
            json.loads(raw[cut:].decode("utf-8-sig"))
        except ValueError:
            self.path.write_bytes(raw[:cut])
        else:
            with self.path.open("ab") as fh:
                fh.write(b"\n")

    def append(self, event: str, **data: str | int | float | bool) -> None:
        with self._lock:
            self._heal()
            recs = self.records()
            prev = recs[-1]["hash"] if recs else _ZERO
            rec = {"t": round(time.time(), 3), "event": event, "data": data, "prev": prev}
            rec["hash"] = _digest(prev, rec)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            if self.anchor is not None:
                self.anchor.save(len(recs) + 1, rec["hash"])

    def verify(self) -> bool:
        prev = _ZERO
        for rec in self.records():
            if rec["prev"] != prev or rec["hash"] != _digest(prev, rec):
                return False
            prev = rec["hash"]
        return True

    def guard(self, now: float | None = None) -> None:
        """Prüft das Protokoll gegen den Kontrollwert. Ohne Kontrollwert passiert nichts."""
        if self.anchor is not None:
            self.anchor.check(self, now)

    def count(self, event: str, within: float, *, domain: str | None = None, now: float | None = None) -> int:
        now = time.time() if now is None else now
        return sum(
            1 for r in self.records()
            if r["event"] == event and r["t"] >= now - within
            and (domain is None or r["data"].get("domain") == domain)
        )

    def last_time(self, event: str) -> float | None:
        times = [r["t"] for r in self.records() if r["event"] == event]
        return max(times) if times else None
