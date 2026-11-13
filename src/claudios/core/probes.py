"""Probe-Phase nach dem Crawl: sammelt Zusatzdaten (DNS, externe Links) in snap.extra.
Die Prüfungen selbst bleiben reine Auswertungen und lösen keine eigenen Anfragen aus."""
from __future__ import annotations

from .dnsprobe import collect_dns
from .errors import ClaudiosError, ErrorCode as E
from .linkprobe import check_external_links


async def gather_probes(gk, snap, resolver) -> None:
    if snap.profile == "quick" or snap.target.loopback or not snap.pages:
        return
    errors: list[str] = []
    try:
        snap.extra["dns"] = await collect_dns(resolver, snap.target.host, snap.target.registrable)
    except Exception as exc:  # noqa: BLE001 – die DNS-Prüfungen werden dann als nicht ausgeführt gemeldet
        errors.append(f"dns:{type(exc).__name__}")
    if gk.cancel is not None and gk.cancel.is_set():
        raise ClaudiosError(E.SCAN_CANCELLED)
    try:
        snap.extra["links"] = await check_external_links(gk, snap)
    except ClaudiosError:
        raise
    except Exception as exc:  # noqa: BLE001
        errors.append(f"links:{type(exc).__name__}")
    if errors:
        snap.extra["probe_errors"] = errors
