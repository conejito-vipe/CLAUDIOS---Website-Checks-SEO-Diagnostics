"""Probe-Phase nach dem Crawl: sammelt Zusatzdaten in snap.extra (DNS, Takeover, ads.txt, externe Links).
Die Prüfungen selbst bleiben reine Auswertungen und lösen keine eigenen Anfragen aus."""
from __future__ import annotations

from .adsprobe import fetch_ads
from .dnsprobe import collect_dns
from .errors import ClaudiosError, ErrorCode as E
from .linkprobe import check_external_links
from .takeoverprobe import collect_takeover


async def gather_probes(gk, snap, resolver) -> None:
    if snap.profile == "quick" or snap.target.loopback or not snap.pages:
        return
    steps = (
        ("dns", lambda: collect_dns(resolver, snap.target.host, snap.target.registrable)),
        ("takeover", lambda: collect_takeover(resolver, snap)),
        ("ads", lambda: fetch_ads(gk, snap)),
        ("links", lambda: check_external_links(gk, snap)),
    )
    errors: list[str] = []
    for name, make in steps:
        if gk.cancel is not None and gk.cancel.is_set():
            raise ClaudiosError(E.SCAN_CANCELLED)
        try:
            snap.extra[name] = await make()
        except ClaudiosError:
            raise
        except Exception as exc:  # noqa: BLE001 – die zugehörigen Prüfungen werden dann als nicht ausgeführt gemeldet
            errors.append(f"{name}:{type(exc).__name__}")
    if errors:
        snap.extra["probe_errors"] = errors