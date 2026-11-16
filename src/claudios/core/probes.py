"""Probe-Phase nach dem Crawl: sammelt Zusatzdaten in snap.extra
(DNS, Takeover, ads.txt, Sitemap, Soft-404, Skripte/Stile, TLS, externe Links).
Die Prüfungen selbst bleiben reine Auswertungen und lösen keine eigenen Anfragen aus."""
from __future__ import annotations

from collections.abc import Callable

from .adsprobe import fetch_ads
from .assetprobe import collect_assets
from .dnsprobe import collect_dns
from .errors import ClaudiosError, ErrorCode as E
from .linkprobe import check_external_links
from .seoprobe import collect_sitemap, probe_soft404
from .takeoverprobe import collect_takeover
from .tlsprobe import probe_tls


async def gather_probes(gk, snap, resolver,
                        progress: Callable[[str, int, int], None] | None = None) -> None:
    if snap.profile == "quick" or snap.target.loopback or not snap.pages:
        return
    steps = (
        ("dns", lambda: collect_dns(resolver, snap.target.host, snap.target.registrable)),
        ("takeover", lambda: collect_takeover(resolver, snap)),
        ("ads", lambda: fetch_ads(gk, snap)),
        ("sitemap", lambda: collect_sitemap(gk, snap)),
        ("soft404", lambda: probe_soft404(gk, snap)),
        ("assets", lambda: collect_assets(gk, snap)),
        ("tls", lambda: probe_tls(resolver, snap)),
        ("links", lambda: check_external_links(gk, snap)),
    )
    report = progress or (lambda *_: None)
    errors: list[str] = []
    for index, (name, make) in enumerate(steps, 1):
        if gk.cancel is not None and gk.cancel.is_set():
            raise ClaudiosError(E.SCAN_CANCELLED)
        report(f"probe:{name}", index, len(steps))
        try:
            snap.extra[name] = await make()
        except ClaudiosError:
            raise
        except Exception as exc:  # noqa: BLE001 – die zugehörigen Prüfungen werden dann als nicht ausgeführt gemeldet
            errors.append(f"{name}:{type(exc).__name__}")
    if errors:
        snap.extra["probe_errors"] = errors