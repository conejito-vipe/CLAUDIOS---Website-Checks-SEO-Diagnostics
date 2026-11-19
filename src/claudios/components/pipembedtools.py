"""Installation von sslyze in die mitgelieferte Python-Laufzeit (nur im Windows-Programm ohne eigenes Python).
Die Laufzeit (Komponente python-runtime) und die pip-Wheel-Datei (pip-wheel) sind über runtime-lock.json mit SHA256
gepinnt. Die Laufzeit wird in den Ordner der Komponente kopiert; ihre ._pth-Datei bekommt die pip-Wheel-Datei und
site-packages (bei einer ._pth-Datei gelten Umgebungsvariablen wie PYTHONPATH nicht). pip läuft wie bei piptools nur mit
--require-hashes und --no-deps aus der festen Liste pip-sslyze.json. Ungeprüft: ob der Bau von sslyze aus dem Quellarchiv
in der eingebetteten Laufzeit gelingt (das zeigt erst der Windows-Build)."""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.toolrunner import run_tool
from . import piptools
from .lock import Component

WHEEL_NAME = "pip.whl"
SITE_LINE = "Lib\\site-packages"
status = piptools.status  # gleiche Prüfung: Marker, Programmdatei und Hash der Liste


def _tool(name: str) -> Path | None:
    from . import manager  # erst hier importiert, weil der Manager dieses Modul dynamisch lädt

    return manager.tool_path(name)


def prepare_runtime(source: Path, target: Path, wheel: Path) -> Path:
    """Kopiert die Laufzeit nach target und schaltet pip.whl und site-packages in der ._pth-Datei ein."""
    if not (source / "python.exe").is_file():
        raise ClaudiosError(E.COMPONENT_MISSING, reason="python-runtime")
    shutil.copytree(source, target)
    pth = next(iter(target.glob("python*._pth")), None)
    if pth is None:
        raise ClaudiosError(E.TOOL_FAILED, reason="python runtime without ._pth file")
    drop = ("#import site", "import site", WHEEL_NAME, SITE_LINE)
    keep = [line for line in pth.read_text("utf-8").splitlines() if line.strip() not in drop]
    pth.write_text("\n".join([*keep, WHEEL_NAME, SITE_LINE, "import site"]) + "\n", "utf-8")
    shutil.copy2(wheel, target / WHEEL_NAME)
    (target / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    return target / "python.exe"


def pip_command(python: Path, requirements: Path, site: Path, name: str) -> list:
    return [python, "-m", "pip", "install", "--require-hashes", "--no-deps", "--only-binary=:all:",
            f"--no-binary={name}", "--disable-pip-version-check", "--index-url", piptools.INDEX_URL,
            "--target", site, "-r", requirements]


def install(comp: Component, *, root: Path | None = None,
            progress: Callable[[str, str, int, int], None] | None = None,
            cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    digest = piptools.lock_hash()
    if not digest:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    runtime, wheel = _tool("python-runtime"), _tool("pip-wheel")
    if runtime is None or wheel is None:
        raise ClaudiosError(E.COMPONENT_MISSING, reason="python-runtime")
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.INSTALL_CANCELLED)
    base = root or paths.tools_dir()
    target = base / comp.name
    try:
        if target.exists():
            shutil.rmtree(target)
        report(comp.name, "download", 0, 1)
        python = prepare_runtime(runtime.parent, target, wheel)
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
            requirements = Path(tmp) / "requirements.txt"
            requirements.write_text(piptools._requirements(), "utf-8")
            result = run_tool(
                pip_command(python, requirements, target / "Lib" / "site-packages", comp.name),
                cwd=tmp, timeout=piptools.PIP_TIMEOUT, root=base,
                extra_env={"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1", "PYTHONNOUSERSITE": "1"})
        if result.returncode != 0:
            raise ClaudiosError(E.TOOL_FAILED, reason=f"pip exit code {result.returncode}")
        (target / piptools.MARKER).write_text(json.dumps({
            "version": comp.version, "sha256": digest,
            "installed": datetime.now(UTC).isoformat(timespec="seconds"),
        }), "utf-8")
        report(comp.name, "extract", 1, 1)
    except (ClaudiosError, OSError) as exc:
        shutil.rmtree(target, ignore_errors=True)  # kein halb installierter Zustand
        if isinstance(exc, ClaudiosError):
            raise
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
