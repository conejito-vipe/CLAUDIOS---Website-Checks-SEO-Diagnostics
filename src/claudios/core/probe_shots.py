"""Screenshots der Startseite (Desktop 1280 px, Mobil 390 px), nur lokal. NUR mit eingeschalteter Option 'screenshots'
(Seite 'Externe Dienste', Standard: aus). Ein eigenes Browser-Skript (components/npm/shot_probe.js) mit denselben
Sicherheitsregeln wie browser_probe.js: Zielhost auf die geprüfte IP festgelegt, kein HTTP, keine lokalen Adressen,
keine Service Worker. Die Bilder liegen im Cache-Ordner 'shots' (die letzten shots_keep Scans), nichts wird gesendet.
Der Lauf zählt zum Werkzeugbudget (core/toolbudget.py)."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from .. import USER_AGENT, paths
from ..components.manager import tool_path
from ..components.npmtools import node_env
from . import options
from .errors import ClaudiosError
from .limits import LIMITS
from .probe_zap import _unchanged
from .toolrunner import run_tool

NAME = "shots"
MIN_LEVEL = 1
ALLOWED_FILES = ("desktop.png", "mobile.png")


class _Skip(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def shots_root() -> Path:
    return paths.cache_dir() / "shots"


def _stem(host: str) -> str:
    return re.sub(r"[^a-z0-9.-]", "-", host.lower())[:60] or "site"


def _node():
    node = tool_path("node")
    browser = paths.tools_dir() / "playwright" / "node_modules" / "playwright"
    return node if node is not None and browser.is_dir() else None


def _pin(snap) -> str:
    from ..checks._browser import _pin_ip  # erst hier: die Prüfungen laden die Probes, nicht umgekehrt
    from ..checks._util import CheckSkipped

    try:
        return _pin_ip(snap)
    except CheckSkipped as skip:
        raise _Skip(skip.reason) from None


def _environment(node) -> dict:
    base = paths.tools_dir() / "playwright"
    env = node_env(Path(node).parent)
    env["NODE_PATH"] = str(base / "node_modules")
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(base / "browsers")
    return env


def _prune(root: Path) -> None:
    folders = sorted(p for p in root.iterdir() if p.is_dir())
    for old in folders[: max(0, len(folders) - LIMITS.shots_keep)]:
        shutil.rmtree(old, ignore_errors=True)


def _run(snap) -> dict:
    urls = [pg.url for pg in snap.docs() if pg.status == 200 and pg.url.startswith("https://")][:1]
    if not urls:
        return {"enabled": True, "skip": "no_pages"}
    node = _node()
    if node is None:
        return {"enabled": True, "skip": "tool_not_found"}
    try:
        ip = _pin(snap)
    except _Skip as skip:
        return {"enabled": True, "skip": skip.reason}
    root = shots_root()
    root.mkdir(parents=True, exist_ok=True)
    outdir = root / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%f')}_{_stem(snap.target.host)}"
    outdir.mkdir()
    timeout = LIMITS.browser_timeout_seconds * 2 + 60.0
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        work = Path(tmp)
        script, source, target = work / "shot_probe.js", work / "in.json", work / "out.json"
        script.write_bytes(resources.files("claudios.components").joinpath("npm").joinpath("shot_probe.js").read_bytes())
        source.write_text(json.dumps({"urls": urls, "host": snap.target.host, "registrable": snap.target.registrable,
                                      "ip": ip, "ua_suffix": USER_AGENT, "outdir": str(outdir)}), "utf-8")
        try:
            run_tool([node, script, source, target], cwd=work, timeout=timeout, extra_env=_environment(node))
        except ClaudiosError:
            shutil.rmtree(outdir, ignore_errors=True)
            return {"enabled": True, "skip": "tool_failed"}
        try:
            data = json.loads(target.read_text("utf-8"))
        except (OSError, ValueError):
            shutil.rmtree(outdir, ignore_errors=True)
            return {"enabled": True, "skip": "tool_output_unreadable"}
    entries = data.get("shots") if isinstance(data, dict) else None
    files = []
    for entry in entries if isinstance(entries, list) else []:
        name = entry.get("file") if isinstance(entry, dict) else None
        path = outdir / str(name)
        if name in ALLOWED_FILES and path.is_file() and 0 < path.stat().st_size <= LIMITS.shot_bytes_max:
            files.append(name)
    if not files:
        shutil.rmtree(outdir, ignore_errors=True)
        return {"enabled": True, "skip": "shots_failed"}
    _prune(root)
    return {"enabled": True, "skip": None, "dir": str(outdir), "files": files}


async def collect(gk, snap, resolver) -> dict:
    if not options.enabled("screenshots"):
        return {"enabled": False, "skip": "shots_disabled"}
    if snap.target.loopback:
        return {"enabled": True, "skip": "localhost"}
    if not await _unchanged(gk):
        return {"enabled": True, "skip": "dns_changed"}
    result = await asyncio.to_thread(_run, snap)
    if not await _unchanged(gk):  # die Bilder stammen eventuell von einem fremden Server: verwerfen, auch auf der Platte
        if result.get("dir"):
            shutil.rmtree(result["dir"], ignore_errors=True)
        return {"enabled": True, "skip": "dns_changed"}
    return result
