from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..checks import load_all
from ..checks._util import CheckSkipped
from .audit_log import AuditLog
from .crawler import crawl
from .errors import ClaudiosError, ErrorCode as E, describe
from .findings import Finding
from .guard import DohResolver, normalize_input
from .net import Gatekeeper
from .probes import gather_probes
from .quota import ScanLock, check_quota
from .registry import REGISTRY
from .scoring import compute_scores
from .snapshot import Snapshot

log = logging.getLogger("claudios.engine")


@dataclass
class ScanResult:
    snapshot: Snapshot
    findings: list[Finding]
    executed: dict[str, str]
    scores: dict
    requests: int = 0
    bytes_total: int = 0
    meta: dict = field(default_factory=dict)


def run_checks(snap: Snapshot, level: int, profile: str,
               components: Callable[[str], bool] = lambda name: False) -> tuple[list[Finding], dict[str, str]]:
    """Ein nicht ausgeführter Check wird NIE als 'bestanden' gewertet."""
    load_all()
    findings: list[Finding] = []
    executed: dict[str, str] = {}
    for cid, rc in sorted(REGISTRY.items()):
        m = rc.meta
        if profile not in m.profiles:
            continue
        if m.kind == "active" and level < 2:  # Verteidigung in der Tiefe: aktive Checks nie ohne Stufe 2
            executed[cid] = "skipped:level2_required"
            continue
        missing = [n for n in m.needs if not components(n)]
        if missing:
            executed[cid] = "skipped:component_missing:" + ",".join(missing)
            continue
        if snap.abort and not snap.pages and cid != "SYS-ABT-001":
            executed[cid] = "skipped:scan_aborted"
            continue
        try:
            findings.extend(rc.fn(snap))
            executed[cid] = "ran"
        except CheckSkipped as skip:  # z. B. fehlende Daten aus der Probe-Phase
            executed[cid] = f"skipped:{skip.reason}"
        except Exception as exc:  # noqa: BLE001
            log.error("check %s failed: %r", cid, exc)
            executed[cid] = f"failed:{E.INTERNAL.value}"
    return findings, executed


def _abort_info(code: E, **ctx: object) -> dict:
    return {"code": code.value, "de": describe(code, "de", **ctx), "en": describe(code, "en", **ctx)}


async def run_scan(raw_url: str, *, level: int, profile: str = "standard", confirmed: bool,
                   audit: AuditLog, lock_path: Path, allow_localhost: bool = False,
                   verified_property: str | None = None, resolver: DohResolver | None = None,
                   progress: Callable[[str, int, int], None] | None = None,
                   cancel: asyncio.Event | None = None,
                   components: Callable[[str], bool] = lambda name: False) -> ScanResult:
    if not confirmed:
        raise ClaudiosError(E.PERM_MISSING)
    if level not in (1, 2) or profile not in ("quick", "standard", "deep"):
        raise ClaudiosError(E.INTERNAL, reason="invalid level/profile")
    if level == 2 and not verified_property:  # die Verifizierung liefert das GSC-Modul (Paket 5)
        raise ClaudiosError(E.PERM_LEVEL2)
    target = normalize_input(raw_url, allow_localhost)
    check_quota(audit, target.registrable, level)
    snap = Snapshot(target=target, level=level, profile=profile)
    requests = bytes_total = 0
    with ScanLock(lock_path):
        doh = resolver or DohResolver()
        gk = Gatekeeper(target, resolver=doh, allow_localhost=allow_localhost, cancel=cancel)
        audit.append("scan_start", domain=target.registrable, level=level, profile=profile)
        try:
            await crawl(gk, snap, progress=progress)
            await gather_probes(gk, snap, doh, progress)
            snap.status = "complete"
        except ClaudiosError as e:
            snap.status, snap.abort = "aborted", _abort_info(e.code, **e.ctx)
        except Exception as exc:  # noqa: BLE001 – nie stumm scheitern
            log.error("scan crashed: %r", exc)
            snap.status, snap.abort = "aborted", _abort_info(E.INTERNAL, reason=type(exc).__name__)
        finally:
            requests, bytes_total = gk.requests, gk.bytes_total
            await gk.aclose()
        snap.finished = time.time()
        findings, executed = run_checks(snap, level, profile, components)
        if snap.status == "complete" and (any(p.error for p in snap.pages) or any(v != "ran" for v in executed.values())):
            snap.status = "limited"
        audit.append("scan_end", domain=target.registrable, status=snap.status)
    return ScanResult(snap, findings, executed, compute_scores(findings, executed),
                      requests=requests, bytes_total=bytes_total)