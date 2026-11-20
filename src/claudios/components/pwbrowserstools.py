"""Installation von Firefox und WebKit für die Browser-Gegenprobe (Playwright). Die Browser kommen in denselben
Ordner wie Chromium (tools/playwright/browsers). Playwright lädt sie von seinem eigenen Server über HTTPS; diese
Dateien sind NICHT durch eine eigene Prüfsumme von Claudios gepinnt (wie bei Chromium). Der Marker dieser Komponente
liegt in tools/pw-browsers und speichert den Hash der Playwright-Sperrdatei. Der Download meldet keinen Fortschritt:
ein Beobachter (dlwatch) schätzt ihn aus dem Wachstum der Ordner."""
from __future__ import annotations

import json
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.toolrunner import run_tool
from . import playwrighttools
from .dlwatch import SizeWatcher
from .lock import Component
from .npmtools import node_env

MARKER = ".claudios-installed.json"
ENGINES = ("firefox", "webkit")
BROWSER_TIMEOUT = 1800.0
EXPECTED_BYTES = 400 * 1024 * 1024  # Schätzung (ungeprüft), nur für die Fortschrittsanzeige


def playwright_dir(root: Path | None = None) -> Path:
    return (root or paths.tools_dir()) / "playwright"


def has_engines(root: Path | None = None) -> bool:
    folder = playwright_dir(root) / "browsers"
    return folder.is_dir() and all(next(iter(folder.glob(f"{name}*")), None) is not None for name in ENGINES)


def _node() -> Path | None:
    from . import manager  # erst hier importiert, weil der Manager dieses Modul dynamisch lädt

    return manager.tool_path("node")


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    digest = playwrighttools.lock_hash()
    if not digest:
        return "not_pinned"
    base = (root or paths.tools_dir()) / comp.name
    try:
        info = json.loads((base / MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return "missing"
    if not has_engines(root):
        return "missing"
    return "installed" if info.get("sha256") == digest else "outdated"


def install(comp: Component, *, root: Path | None = None,
            progress: Callable[[str, str, int, int], None] | None = None,
            cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    digest = playwrighttools.lock_hash()
    if not digest:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    node = _node()
    cli = playwright_dir(root) / "node_modules" / "playwright" / "cli.js"
    if node is None:
        raise ClaudiosError(E.COMPONENT_MISSING, reason="node")
    if not cli.is_file():
        raise ClaudiosError(E.COMPONENT_MISSING, reason="playwright")
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.INSTALL_CANCELLED)
    base = root or paths.tools_dir()
    try:
        report(comp.name, "download", 0, 100)
        env = node_env(node.parent)
        browsers = playwright_dir(root) / "browsers"
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
            env["TMP"] = env["TEMP"] = env["TMPDIR"] = tmp
            with SizeWatcher([browsers, Path(tmp)], EXPECTED_BYTES,
                             lambda done, total: report(comp.name, "download", done, total), base=0, span=95):
                result = run_tool([node, cli, "install", *ENGINES], cwd=playwright_dir(root),
                                  timeout=BROWSER_TIMEOUT, root=base, extra_env=env)
        if result.returncode != 0:
            raise ClaudiosError(E.TOOL_FAILED, reason=f"browser download exit code {result.returncode}")
        if not has_engines(root):
            raise ClaudiosError(E.TOOL_FAILED, reason="browsers missing after the download")
        target = base / comp.name
        target.mkdir(parents=True, exist_ok=True)
        (target / MARKER).write_text(json.dumps({
            "version": comp.version, "sha256": digest,
            "installed": datetime.now(UTC).isoformat(timespec="seconds"),
        }), "utf-8")
        report(comp.name, "extract", 1, 1)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
