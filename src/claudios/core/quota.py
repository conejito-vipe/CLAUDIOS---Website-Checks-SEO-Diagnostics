from __future__ import annotations

import time

from .audit_log import AuditLog
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

try:  # Windows
    import msvcrt

    def _lock(fh) -> None:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
except ImportError:  # Linux/macOS (z. B. CI)
    import fcntl

    def _lock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def check_quota(log: AuditLog, domain: str, level: int, now: float | None = None) -> None:
    now = time.time() if now is None else now
    last = log.last_time("scan_start")
    if last is not None and now - last < LIMITS.cooldown_seconds:
        raise ClaudiosError(E.LIMIT_COOLDOWN, seconds=LIMITS.cooldown_seconds)
    if log.count("scan_start", 3600, now=now) >= LIMITS.scans_per_hour:
        raise ClaudiosError(E.LIMIT_HOURLY, limit=LIMITS.scans_per_hour)
    if level == 1 and log.count("scan_start", 86400, domain=domain, now=now) >= LIMITS.scans_per_domain_day_level1:
        raise ClaudiosError(E.LIMIT_DOMAIN_DAY, limit=LIMITS.scans_per_domain_day_level1)


class ScanLock:
    """Nur ein Scan gleichzeitig (Dateisperre; das Betriebssystem löst sie bei einem Absturz automatisch)."""

    def __init__(self, path) -> None:
        self.path, self._fh = path, None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")  # noqa: SIM115
        try:
            _lock(self._fh)
        except OSError:
            self._fh.close()
            raise ClaudiosError(E.LIMIT_BUSY) from None
        return self

    def __exit__(self, *exc) -> None:
        if self._fh:
            self._fh.close()
