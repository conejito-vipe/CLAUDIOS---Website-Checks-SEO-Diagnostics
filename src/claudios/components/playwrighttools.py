"""Installation von Playwright, axe-core und Chromium: die npm-Pakete kommen aus einer festen Sperrdatei (npm ci
--ignore-scripts, nur gegen die offizielle Registry über HTTPS, Prüfsummen von npm). Danach lädt Playwright den
Chromium-Browser von seinem eigenen Server (HTTPS). Diese Browser-Datei ist NICHT durch eine eigene Prüfsumme von
Claudios gepinnt. Das Handbuch weist darauf hin. Der Browser-Download meldet keinen Fortschritt: ein Beobachter
(dlwatch) schätzt ihn aus dem Wachstum der Ordner."""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
from collections.abc import Callable
from importlib import resources
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.toolrunner import run_tool
from ._shared import marker_status, replace_dir, require_cancel_free, require_npm, require_pinned, write_marker
from .dlwatch import SizeWatcher
from .lock import Component
from .npmtools import node_env

REGISTRY_URL = "https://registry.npmjs.org/"
FILES = (("pw-package.json", "package.json"), ("pw-package-lock.json", "package-lock.json"),
         ("browser_probe.js", "browser_probe.js"))
NPM_TIMEOUT = 900.0
BROWSER_TIMEOUT = 1800.0
EXPECTED_BYTES = 400 * 1024 * 1024  # Schätzung (ungeprüft), nur für die Fortschrittsanzeige


def _resource_bytes(name: str) -> bytes:
    return resources.files("claudios.components").joinpath("npm").joinpath(name).read_bytes()


def lock_hash() -> str:
    """SHA256 der mitgelieferten Sperrdatei; leer, wenn sie fehlt oder keine Pakete enthält."""
    try:
        data = _resource_bytes("pw-package-lock.json")
        packages = json.loads(data).get("packages") or {}
    except (OSError, ValueError, AttributeError):
        return ""
    if not any(str(key).startswith("node_modules/") for key in packages):
        return ""
    return hashlib.sha256(data).hexdigest()


def _node_exe() -> Path | None:
    from . import manager  # erst hier importiert, weil der Manager dieses Modul dynamisch lädt

    return manager.tool_path("node")


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    return marker_status(comp, lock_hash(), root, lambda base: next(iter((base / "browsers").glob("chromium*")), None) is not None)


def install(comp: Component, *, root: Path | None = None,
            progress: Callable[[str, str, int, int], None] | None = None,
            cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    digest = lock_hash()
    require_pinned(comp, digest)
    node = _node_exe()
    npm_cli = require_npm(node)
    require_cancel_free(cancel)
    target = (root or paths.tools_dir()) / comp.name
    try:
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp_name:
            stage = Path(tmp_name) / "stage"
            stage.mkdir()
            for source, name in FILES:
                (stage / name).write_bytes(_resource_bytes(source))
            report(comp.name, "download", 0, 100)
            env = node_env(node.parent)
            result = run_tool(
                [node, npm_cli, "ci", "--ignore-scripts", "--no-audit", "--no-fund",
                 "--registry", REGISTRY_URL, "--cache", env["npm_config_cache"]],
                cwd=stage, timeout=NPM_TIMEOUT, extra_env=env)
            if result.returncode != 0:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"npm ci exit code {result.returncode}")
            cli = stage / "node_modules" / "playwright" / "cli.js"
            if not cli.is_file():
                raise ClaudiosError(E.TOOL_FAILED, reason=f"{comp.name}: {comp.exe} not found")
            if cancel is not None and cancel.is_set():
                raise ClaudiosError(E.INSTALL_CANCELLED)
            report(comp.name, "download", 50, 100)
            browsers = stage / "browsers"
            download_tmp = Path(tmp_name) / "dl"  # eigener Temp-Ordner: dort liegt die Zip-Datei während des Downloads
            download_tmp.mkdir()
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
            env["TMP"] = env["TEMP"] = env["TMPDIR"] = str(download_tmp)
            with SizeWatcher([browsers, download_tmp], EXPECTED_BYTES,
                             lambda done, total: report(comp.name, "download", done, total)):
                result = run_tool([node, cli, "install", "chromium"], cwd=stage, timeout=BROWSER_TIMEOUT,
                                  extra_env=env)
            if result.returncode != 0:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"browser download exit code {result.returncode}")
            write_marker(stage, comp, digest)
            replace_dir(stage, target)
            report(comp.name, "extract", 1, 1)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
