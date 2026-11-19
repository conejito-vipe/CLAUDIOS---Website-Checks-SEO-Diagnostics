"""Firefox und WebKit (Playwright) als Gegenprobe zu Chromium, nur im Profil Tief. Ein eigenes Skript
(components/npm/engine_probe.js) lädt höchstens PAGES Seiten in beiden Browsern. Der Lauf zählt zum Werkzeugbudget
(core/toolbudget.py). Anders als bei Chromium lässt sich der Zielhost nicht an die geprüfte IP festlegen: Claudios prüft
die Auflösung vor und nach dem Lauf (core/rebind.py) und danach die beobachteten Fremd-Hosts (core/foreign.py).
Grenze: Das erkennt einen Wechsel, verhindert ihn aber nicht mitten im Lauf. Ausgewertet in checks/enginechecks.py."""
from __future__ import annotations

import asyncio
import json
import tempfile
from importlib import resources
from pathlib import Path

from .. import USER_AGENT, paths
from ..components.manager import tool_path
from ..components.npmtools import node_env
from ..components.pwbrowserstools import has_engines
from . import foreign
from .errors import ClaudiosError
from .limits import LIMITS
from .probe_zap import _unchanged
from .toolrunner import run_tool

NAME = "engines"
MIN_LEVEL = 1
PAGES = 3
ENGINES = ("firefox", "webkit")


def _node():
    node = tool_path("node")
    ready = (paths.tools_dir() / "playwright" / "node_modules" / "playwright").is_dir() and has_engines()
    return node if node is not None and ready else None


def _environment(node) -> dict:
    base = paths.tools_dir() / "playwright"
    env = node_env(Path(node).parent)
    env["NODE_PATH"] = str(base / "node_modules")
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(base / "browsers")
    return env


def clean(data) -> dict | None:
    """Behält nur erwartete Engines und Seiten-Einträge; None, wenn die Ausgabe nicht brauchbar ist."""
    engines = data.get("engines") if isinstance(data, dict) else None
    if not isinstance(engines, list):
        return None
    out = []
    for item in engines[:3]:
        if not isinstance(item, dict) or item.get("engine") not in ENGINES:
            continue
        pages = item.get("pages")
        out.append({"engine": item["engine"], "version": str(item.get("version", ""))[:20],
                    "error": str(item["error"])[:120] if item.get("error") else None,
                    "pages": [p for p in (pages if isinstance(pages, list) else []) if isinstance(p, dict)][:PAGES]})
    return {"engines": out} if out else None


def finish(data, look=None) -> dict:
    """Säubert die Ausgabe, prüft die beobachteten Fremd-Hosts erneut und verwirft Daten auffälliger Hosts."""
    cleaned = clean(data)
    if cleaned is None:
        return {"skip": "tool_output_unreadable"}
    if all(e["error"] and not e["pages"] for e in cleaned["engines"]):
        return {"skip": "browser_failed"}
    pages = [p for e in cleaned["engines"] for p in e["pages"]]
    hosts = {str(h) for p in pages if isinstance(p.get("third_party"), dict) for h in p["third_party"]}
    found = foreign.screen(hosts, look or foreign.lookup)
    if found.private:
        bad = set(found.private)
        for page in pages:
            foreign._drop(page, bad)
        cleaned["foreign_private"] = list(found.private)
    if found.unchecked:
        cleaned["foreign_unchecked"] = found.unchecked
    return {"skip": None, **cleaned}


def _run(snap) -> dict:
    from ..checks._browser import sample_urls  # erst hier importiert: die Prüfungen laden die Probes, nicht umgekehrt

    urls = sample_urls(snap)[:PAGES]
    if not urls:
        return {"skip": "no_pages"}
    node = _node()
    if node is None:
        return {"skip": "tool_not_found"}
    payload = {"urls": urls, "registrable": snap.target.registrable, "ua_suffix": USER_AGENT}
    timeout = min(LIMITS.browser_timeout_seconds * len(urls) * len(ENGINES) + 120.0, 1800.0)
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        work = Path(tmp)
        script, source, target = work / "engine_probe.js", work / "in.json", work / "out.json"
        script.write_bytes(resources.files("claudios.components").joinpath("npm").joinpath("engine_probe.js").read_bytes())
        source.write_text(json.dumps(payload), "utf-8")
        try:
            run_tool([node, script, source, target], cwd=work, timeout=timeout, extra_env=_environment(node))
        except ClaudiosError:
            return {"skip": "tool_failed"}
        try:
            data = json.loads(target.read_text("utf-8"))
        except (OSError, ValueError, RecursionError):
            return {"skip": "tool_output_unreadable"}
    return finish(data)


async def collect(gk, snap, resolver) -> dict:
    if snap.profile != "deep":
        return {"skip": "profile_not_deep"}
    if snap.target.loopback:
        return {"skip": "localhost"}
    if not await _unchanged(gk):
        return {"skip": "dns_changed"}
    result = await asyncio.to_thread(_run, snap)
    if not await _unchanged(gk):
        return {"skip": "dns_changed"}  # die Ergebnisse stammen eventuell von einem fremden Server: verwerfen
    return result
