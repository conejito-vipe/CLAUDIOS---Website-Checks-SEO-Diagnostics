"""Audit-Log mit Hash-Kette. Nur Zeit, Ereignis, Domain, Stufe, Profil. Keine personenbezogenen Daten."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

_ZERO = "0" * 64


def _digest(prev: str, rec: dict) -> str:
    body = json.dumps({k: rec[k] for k in ("t", "event", "data")}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256((prev + body).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text("utf-8").splitlines() if x.strip()]

    def append(self, event: str, **data: str | int | float | bool) -> None:
        with self._lock:
            recs = self.records()
            prev = recs[-1]["hash"] if recs else _ZERO
            rec = {"t": round(time.time(), 3), "event": event, "data": data, "prev": prev}
            rec["hash"] = _digest(prev, rec)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=True) + "\n")

    def verify(self) -> bool:
        prev = _ZERO
        for rec in self.records():
            if rec["prev"] != prev or rec["hash"] != _digest(prev, rec):
                return False
            prev = rec["hash"]
        return True

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
