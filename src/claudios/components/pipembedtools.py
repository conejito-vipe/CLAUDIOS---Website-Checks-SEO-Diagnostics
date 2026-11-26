"""Installation von sslyze in die mitgelieferte Python-Laufzeit (nur im Windows-Programm ohne eigenes Python). Die Laufzeit
(Komponente python-runtime) und die pip-Wheel-Datei (pip-wheel) sind über runtime-lock.json mit SHA256 gepinnt. Die Laufzeit
wird in den Ordner der Komponente kopiert; ihre ._pth-Datei bekommt die pip-Wheel-Datei und site-packages (bei einer
._pth-Datei gelten Umgebungsvariablen wie PYTHONPATH nicht). Zusätzlich wird pip nach site-packages entpackt, weil
„python -m pip" im Windows-Lauf „No module named pip" meldete. pip läuft nur mit --require-hashes und --no-deps aus der
festen Liste pip-sslyze.json.

Gibt es sslyze-wheel.json (vom Workflow „sslyze-Wheel erzeugen"), wird sslyze als fertiges Wheel mit SHA256-Prüfung geladen
und ohne Bauen installiert; danach läuft „import sslyze" als Gesundheitstest. Sonst gilt der alte Weg (Bau aus dem
Quellarchiv). Ungeprüft: ob das unter Windows gelingt. Fehler, das Ende der pip-Ausgabe und bei pip-Fehlern sys.path samt
._pth-Datei stehen im Protokoll."""
from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.toolrunner import run_tool
from . import piptools, sslyzewheel
from ._shared import write_marker
from .lock import Component, host_platform

WHEEL_NAME = "pip.whl"
SITE_LINE = "Lib\\site-packages"
ENV = {"PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1", "PYTHONNOUSERSITE": "1"}
status = piptools.status  # gleiche Prüfung: Marker, Programmdatei und Hash der Liste
log = logging.getLogger("claudios")


def _tool(name: str) -> Path | None:
    from . import manager  # erst hier importiert, weil der Manager dieses Modul dynamisch lädt

    return manager.tool_path(name)


def _tail(result) -> str:
    for name in ("stderr", "stdout"):
        data = getattr(result, name, None)
        if data:
            text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
            return text.strip()[-1500:]
    return ""


def _fail(what: str, result) -> ClaudiosError:
    code = getattr(result, "returncode", "?")
    log.error("%s failed (exit code %s): %s", what, code, _tail(result))
    return ClaudiosError(E.TOOL_FAILED, reason=f"{what} exit code {code}")


def _diagnose(python: Path, tmp: str, base: Path) -> None:
    """Schreibt sys.path und die ._pth-Datei ins Protokoll, damit ein pip-Fehler Daten liefert."""
    try:
        result = run_tool([python, "-c", "import sys; print(sys.path)"], cwd=tmp, timeout=60.0, root=base, extra_env=ENV)
        log.error("embedded python sys.path: %s", _tail(result))
        pth = next(iter(python.parent.glob("python*._pth")), None)
        if pth is not None:
            log.error("%s: %s", pth.name, pth.read_text("utf-8", errors="replace").replace("\n", " | "))
    except Exception as exc:  # noqa: BLE001 – die Diagnose darf nie selbst scheitern
        log.error("diagnostic failed: %r", exc)


def runtime_root(exe: Path) -> Path:
    """Der Ordner der Laufzeit: Windows neben python.exe, Mac zwei Ebenen über bin/python3."""
    return exe.parent.parent if host_platform() == "macos" else exe.parent


def site_dir(target: Path) -> Path:
    if host_platform() == "macos":
        return next(iter(sorted(target.glob("lib/python3.*/site-packages"))), target / "lib" / "python3" / "site-packages")
    return target / "Lib" / "site-packages"


def prepare_mac_runtime(source: Path, target: Path) -> Path:
    """Mac: vollständiges Python mit pip (python-build-standalone). Kopie mit relativen Links, keine Änderung nötig."""
    if not (source / "bin" / "python3").exists():
        raise ClaudiosError(E.COMPONENT_MISSING, reason="python-runtime")
    shutil.copytree(source, target, symlinks=True)
    site = site_dir(target)
    site.mkdir(parents=True, exist_ok=True)
    return target / "bin" / "python3"


def prepare_runtime(source: Path, target: Path, wheel: Path | None) -> Path:
    """Kopiert die Laufzeit nach target und schaltet pip.whl und site-packages in der ._pth-Datei ein (Windows)."""
    if host_platform() == "macos":
        return prepare_mac_runtime(source, target)
    if wheel is None or not (source / "python.exe").is_file():
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


def _unpack_pip(target: Path, site: Path) -> None:
    """pip zusätzlich als normales Paket nach site-packages entpacken (Wheel ist eine ZIP-Datei, SHA256 schon geprüft)."""
    from . import manager

    try:
        manager.extract(target / WHEEL_NAME, site, False)
    except ClaudiosError as exc:
        log.warning("pip wheel could not be unpacked, pip is used from the wheel file: %s", exc)


def pip_command(python: Path, requirements: Path, site: Path, name: str) -> list:
    return [python, "-m", "pip", "install", "--require-hashes", "--no-deps", "--only-binary=:all:",
            f"--no-binary={name}", "--disable-pip-version-check", "--index-url", piptools.INDEX_URL,
            "--target", site, "-r", requirements]


def deps_command(python: Path, requirements: Path, site: Path) -> list:
    """Alle Abhängigkeiten (nur fertige Wheels, mit Prüfsummen), ohne das Werkzeug selbst."""
    return [python, "-m", "pip", "install", "--require-hashes", "--no-deps", "--only-binary=:all:",
            "--disable-pip-version-check", "--index-url", piptools.INDEX_URL, "--target", site, "-r", requirements]


def wheel_command(python: Path, wheel: Path, site: Path) -> list:
    """Das bereits per SHA256 geprüfte Wheel, ohne Index und ohne Abhängigkeiten."""
    return [python, "-m", "pip", "install", "--no-deps", "--no-index", "--disable-pip-version-check",
            "--target", site, wheel]


def _install_pinned(comp: Component, pin: dict, python: Path, site: Path, text: str, tmp: str, base: Path,
                    report, cancel) -> None:
    from . import manager

    wheel = Path(tmp) / pin["filename"]
    manager.download(replace(comp, url=pin["url"], sha256=pin["sha256"], size=pin["size"]), wheel,
                     progress=report, cancel=cancel)
    requirements = Path(tmp) / "requirements.txt"
    requirements.write_text(sslyzewheel.without_requirement(text, comp.name), "utf-8")
    result = run_tool(deps_command(python, requirements, site), cwd=tmp, timeout=piptools.PIP_TIMEOUT, root=base,
                      extra_env=ENV)
    if result.returncode != 0:
        error = _fail("pip dependencies", result)
        _diagnose(python, tmp, base)
        raise error
    result = run_tool(wheel_command(python, wheel, site), cwd=tmp, timeout=piptools.PIP_TIMEOUT, root=base,
                      extra_env=ENV)
    if result.returncode != 0:
        raise _fail("pip wheel", result)
    result = run_tool([python, "-c", "import sslyze"], cwd=tmp, timeout=120.0, root=base, extra_env=ENV)
    if result.returncode != 0:
        raise _fail("sslyze import", result)


def install(comp: Component, *, root: Path | None = None,
            progress: Callable[[str, str, int, int], None] | None = None,
            cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    digest = piptools.lock_hash()
    if not digest:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    mac = host_platform() == "macos"
    runtime, wheel = _tool("python-runtime"), _tool("pip-wheel")
    if runtime is None or (wheel is None and not mac):
        raise ClaudiosError(E.COMPONENT_MISSING, reason="python-runtime")
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.INSTALL_CANCELLED)
    base = root or paths.tools_dir()
    target = base / comp.name
    try:
        if target.exists():
            shutil.rmtree(target)
        report(comp.name, "download", 0, 1)
        python = prepare_runtime(runtime_root(runtime), target, wheel)
        site = site_dir(target)
        if not mac:
            _unpack_pip(target, site)
        text = piptools._requirements()
        pin = sslyzewheel.load_pin()
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
            if pin:
                _install_pinned(comp, pin, python, site, text, tmp, base, report, cancel)
            else:
                requirements = Path(tmp) / "requirements.txt"
                requirements.write_text(text, "utf-8")
                result = run_tool(pip_command(python, requirements, site, comp.name), cwd=tmp,
                                  timeout=piptools.PIP_TIMEOUT, root=base, extra_env=ENV)
                if result.returncode != 0:
                    error = _fail("pip", result)
                    _diagnose(python, tmp, base)
                    raise error
        write_marker(target, comp, digest)
        report(comp.name, "extract", 1, 1)
    except (ClaudiosError, OSError) as exc:
        shutil.rmtree(target, ignore_errors=True)  # kein halb installierter Zustand
        if isinstance(exc, ClaudiosError):
            raise
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
