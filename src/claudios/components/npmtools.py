"""Installation der npm-Werkzeuge (ESLint, Stylelint, retire.js) aus einer festen package-lock.json:
npm prüft damit die Prüfsumme jedes Pakets. Lauf nur mit --ignore-scripts, nur gegen die offizielle
Registry über HTTPS, mit dem portablen Node aus dem Werkzeugordner."""
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
from .lock import Component

REGISTRY_URL = "https://registry.npmjs.org/"
NPM_FILES = ("package.json", "package-lock.json", "eslint.config.mjs", "stylelint.config.json")
NPM_TIMEOUT = 900.0


def _resource_bytes(name: str) -> bytes:
    return resources.files("claudios.components").joinpath("npm").joinpath(name).read_bytes()


def lock_hash() -> str:
    """SHA256 der mitgelieferten package-lock.json; leer, wenn sie fehlt oder keine Pakete enthält."""
    try:
        data = _resource_bytes("package-lock.json")
        packages = json.loads(data).get("packages") or {}
    except (OSError, ValueError, AttributeError):
        return ""
    if not any(str(key).startswith("node_modules/") for key in packages):
        return ""
    return hashlib.sha256(data).hexdigest()


def _node_exe() -> Path | None:
    from . import manager  # erst hier importiert, weil manager dieses Modul lädt

    return manager.tool_path("node")


def node_env(node_dir: Path | None = None) -> dict[str, str]:
    """Eigenes Home im Cache: die Werkzeuge schreiben nichts in dein Benutzerprofil."""
    home = paths.cache_dir() / "nodehome"
    home.mkdir(parents=True, exist_ok=True)
    env = {"HOME": str(home), "USERPROFILE": str(home), "npm_config_cache": str(home / "npm"),
           "npm_config_update_notifier": "false", "npm_config_audit": "false"}
    if node_dir is not None:
        env["PATH"] = str(node_dir)
    return env


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    return marker_status(comp, lock_hash(), root)


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
            for name in NPM_FILES:
                (stage / name).write_bytes(_resource_bytes(name))
            report(comp.name, "download", 0, 1)
            env = node_env(node.parent)
            result = run_tool(
                [node, npm_cli, "ci", "--ignore-scripts", "--no-audit", "--no-fund",
                 "--registry", REGISTRY_URL, "--cache", env["npm_config_cache"]],
                cwd=stage, timeout=NPM_TIMEOUT, extra_env=env)
            if result.returncode != 0:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"npm ci exit code {result.returncode}")
            if next(iter(stage.glob(comp.exe)), None) is None:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"{comp.name}: {comp.exe} not found")
            write_marker(stage, comp, digest)
            replace_dir(stage, target)
            report(comp.name, "extract", 1, 1)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None