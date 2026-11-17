"""Gemeinsamer Browser-Lauf für die Browser-Prüfungen: ein einziger Chromium-Lauf pro Scan (Playwright, externer
Prozess) über eine Stichprobe der gecrawlten Seiten. Das Ergebnis wird im Snapshot zwischengespeichert, auch ein
Fehlschlag, damit nicht jede Prüfung den Browser neu startet. Dateien mit Unterstrich lädt der Prüfungs-Lader nicht."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .. import USER_AGENT, paths
from ..components.manager import tool_path
from ..components.npmtools import node_env
from ..core.errors import ClaudiosError
from ..core.guard import DohResolver, ip_allowed
from ..core.limits import LIMITS
from ..core.toolrunner import run_tool
from ._util import CheckSkipped


def sample_urls(snap) -> list[str]:
    cap = LIMITS.browser_sample_deep if snap.profile == "deep" else LIMITS.browser_sample_standard
    urls: list[str] = []
    for pg in snap.docs():
        if pg.status == 200 and pg.url.startswith("https://") and pg.url not in urls:
            urls.append(pg.url)
        if len(urls) >= cap:
            break
    return urls


def _lookup(host: str, rtype: str) -> list[str]:
    try:
        return DohResolver()._query(host, rtype)
    except Exception:  # noqa: BLE001 – ein DNS-Fehler bedeutet nur: nicht prüfbar
        return []


def _pin_ip(snap) -> str:
    """Eine per DoH aufgelöste, als öffentlich geprüfte IPv4-Adresse, auf die der Browser den Zielhost festlegt."""
    host = snap.target.host
    v4, v6 = _lookup(host, "A"), _lookup(host, "AAAA")
    if not v4:
        raise CheckSkipped("target_no_ipv4")
    if not all(ip_allowed(ip) for ip in v4 + v6):
        raise CheckSkipped("target_not_public")
    return v4[0]


def _run(snap) -> dict:
    if snap.target.loopback:
        raise CheckSkipped("localhost")
    urls = sample_urls(snap)
    if not urls:
        return {"browser": "", "error": None, "pages": []}
    node = tool_path("node")
    base = paths.tools_dir() / "playwright"
    script = base / "browser_probe.js"
    if node is None or not script.is_file():
        raise CheckSkipped("tool_not_found")
    payload = {"urls": urls, "host": snap.target.host, "registrable": snap.target.registrable,
               "ip": _pin_ip(snap), "ua_suffix": USER_AGENT, "axe": True}
    timeout = min(LIMITS.browser_timeout_seconds * len(urls) + 120.0, 1800.0)
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        source, target = Path(tmp) / "in.json", Path(tmp) / "out.json"
        source.write_text(json.dumps(payload), "utf-8")
        env = node_env(node.parent)
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(base / "browsers")
        try:
            run_tool([node, script, source, target], cwd=tmp, timeout=timeout, extra_env=env)
        except ClaudiosError:
            raise CheckSkipped("tool_failed") from None
        try:
            data = json.loads(target.read_text("utf-8"))
        except (OSError, ValueError):
            raise CheckSkipped("tool_output_unreadable") from None
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise CheckSkipped("tool_output_unreadable")
    if data.get("error") and not data["pages"]:
        raise CheckSkipped("browser_failed")
    return data


def browser_data(snap) -> dict:
    cached = snap.extra.get("browser")
    if cached is not None:
        if cached.get("error_reason"):
            raise CheckSkipped(cached["error_reason"])
        return cached
    try:
        data = _run(snap)
    except CheckSkipped as skip:
        snap.extra["browser"] = {"error_reason": skip.reason, "pages": []}
        raise
    snap.extra["browser"] = data
    return data
