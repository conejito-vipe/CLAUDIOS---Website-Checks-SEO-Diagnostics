"""Installation von Python-Werkzeugen (sslyze) in eine eigene, isolierte Umgebung.
pip läuft nur mit --require-hashes und --no-deps aus einer festen Liste (components/pip-sslyze.json),
nur gegen die offizielle Registry über HTTPS. Ohne Prüfsummen in der Liste wird nichts installiert."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.toolrunner import run_tool
from .lock import Component

MARKER = ".claudios-installed.json"
INDEX_URL = "https://pypi.org/simple"
PIP_TIMEOUT = 900.0
VENV_TIMEOUT = 300.0


def _resource_text() -> str:
    return resources.files("claudios.components").joinpath("pip-sslyze.json").read_text("utf-8")


def _requirements() -> str:
    """Der Text der Anforderungsliste; leer, wenn sie fehlt oder keine Prüfsummen enthält."""
    try:
        text = json.loads(_resource_text())["requirements"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    return text if isinstance(text, str) and "--hash=sha256:" in text else ""


def lock_hash() -> str:
    text = _requirements()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _base_python() -> Path:
    if getattr(sys, "frozen", False):
        raise ClaudiosError(E.COMPONENT_MISSING, reason="python")
    return Path(sys.executable)


def _make_venv(python: Path, target: Path) -> None:
    try:
        proc = subprocess.run([str(python), "-m", "venv", str(target)], capture_output=True, shell=False,
                              timeout=VENV_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ClaudiosError(E.TOOL_FAILED, reason="venv") from None
    if proc.returncode != 0:
        raise ClaudiosError(E.TOOL_FAILED, reason="venv")


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    digest = lock_hash()
    if not digest:
        return "not_pinned"
    base = (root or paths.tools_dir()) / comp.name
    try:
        info = json.loads((base / MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return "missing"
    if next(iter(base.glob(comp.exe)), None) is None:
        return "missing"
    return "installed" if info.get("sha256") == digest else "outdated"


def install(comp: Component, *, root: Path | None = None,
            progress: Callable[[str, str, int, int], None] | None = None,
            cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    digest = lock_hash()
    if not digest:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    python = _base_python()
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.INSTALL_CANCELLED)
    base = root or paths.tools_dir()
    target = base / comp.name
    try:
        if target.exists():
            shutil.rmtree(target)
        report(comp.name, "download", 0, 1)
        _make_venv(python, target)
        venv_python = next(iter(target.glob(comp.exe)), None)
        if venv_python is None:
            raise ClaudiosError(E.TOOL_FAILED, reason=f"{comp.name}: {comp.exe} not found")
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
            requirements = Path(tmp) / "requirements.txt"
            requirements.write_text(_requirements(), "utf-8")
            result = run_tool(
                [venv_python, "-m", "pip", "install", "--require-hashes", "--no-deps", "--only-binary=:all:",
                 "--disable-pip-version-check", "--index-url", INDEX_URL, "-r", requirements],
                cwd=tmp, timeout=PIP_TIMEOUT, root=base,
                extra_env={"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1", "PYTHONNOUSERSITE": "1"})
        if result.returncode != 0:
            raise ClaudiosError(E.TOOL_FAILED, reason=f"pip exit code {result.returncode}")
        (target / MARKER).write_text(json.dumps({
            "version": comp.version, "sha256": digest,
            "installed": datetime.now(UTC).isoformat(timespec="seconds"),
        }), "utf-8")
        report(comp.name, "extract", 1, 1)
    except (ClaudiosError, OSError) as exc:
        shutil.rmtree(target, ignore_errors=True)  # kein halb installierter Zustand
        if isinstance(exc, ClaudiosError):
            raise
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None