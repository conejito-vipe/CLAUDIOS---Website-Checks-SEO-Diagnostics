"""Komponenten-Manager: Download nur per HTTPS mit SHA256-Prüfung, sicheres Entpacken, Installation, Entfernen.
Ungeprüfte Komponenten (ohne Prüfsumme in der Lock-Datei) werden nie installiert."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin

import httpx

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from .lock import Component, load_lock

MAX_DOWNLOAD = 700 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
MAX_FILES = 50_000
MARKER = ".claudios-installed.json"
_REDIRECTS = {301, 302, 303, 307, 308}
Progress = Callable[[str, str, int, int], None]


# ---------------------------------------------------------------- Status


def find_exe(comp: Component, base: Path) -> Path | None:
    return next(iter(base.glob(comp.exe)), None)


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    if not comp.sha256:
        return "not_pinned"
    base = (root or paths.tools_dir()) / comp.name
    try:
        info = json.loads((base / MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return "missing"
    if find_exe(comp, base) is None:
        return "missing"
    if info.get("sha256") != comp.sha256 or info.get("version") != comp.version:
        return "outdated"
    return "installed"


def component_checker(root: Path | None = None, lock: list[Component] | None = None) -> Callable[[str], bool]:
    comps = {c.name: c for c in (load_lock() if lock is None else lock)}

    def available(name: str) -> bool:
        comp = comps.get(name)
        return comp is not None and status(comp, root) == "installed"

    return available


def tool_path(name: str, lock: list[Component] | None = None, root: Path | None = None) -> Path | None:
    comps = {c.name: c for c in (load_lock() if lock is None else lock)}
    comp = comps.get(name)
    if comp is None:
        return None
    return find_exe(comp, (root or paths.tools_dir()) / name)


# ---------------------------------------------------------------- Download


def _content_length(value: str | None, fallback: int) -> int:
    try:
        return int(value) if value else fallback
    except ValueError:
        return fallback


def download(comp: Component, dest: Path, *, client: httpx.Client | None = None,
             progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
    if not comp.sha256:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    if not comp.url.startswith("https://"):
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="HTTPS required")
    report = progress or (lambda *_: None)
    own = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=False, trust_env=False)
    digest = hashlib.sha256()
    url = comp.url
    try:
        for _hop in range(6):
            with http.stream("GET", url) as resp:
                if resp.status_code in _REDIRECTS:
                    url = urljoin(url, resp.headers.get("location", ""))
                    if not url.startswith("https://"):
                        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="redirect without HTTPS")
                    continue
                if resp.status_code != 200:
                    raise ClaudiosError(E.DOWNLOAD_FAILED, reason=f"HTTP {resp.status_code}")
                total = _content_length(resp.headers.get("content-length"), comp.size)
                if total > MAX_DOWNLOAD:
                    raise ClaudiosError(E.DOWNLOAD_FAILED, reason="file too large")
                done = 0
                with dest.open("wb") as out:
                    for chunk in resp.iter_bytes(65536):
                        if cancel is not None and cancel.is_set():
                            raise ClaudiosError(E.INSTALL_CANCELLED)
                        done += len(chunk)
                        if done > MAX_DOWNLOAD:
                            raise ClaudiosError(E.DOWNLOAD_FAILED, reason="file too large")
                        digest.update(chunk)
                        out.write(chunk)
                        report(comp.name, "download", done, total)
                break
        else:
            raise ClaudiosError(E.DOWNLOAD_FAILED, reason="too many redirects")
    except httpx.HTTPError as exc:
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason=type(exc).__name__) from None
    finally:
        if own:
            http.close()
    report(comp.name, "verify", 1, 1)
    if digest.hexdigest() != comp.sha256.lower():
        dest.unlink(missing_ok=True)
        raise ClaudiosError(E.CHECKSUM_MISMATCH, reason=comp.name)


# ---------------------------------------------------------------- Entpacken


def _clean_parts(name: str) -> tuple[str, ...]:
    norm = name.replace("\\", "/")
    parts = PurePosixPath(norm).parts
    if norm.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
        raise ClaudiosError(E.UNSAFE_ARCHIVE, reason=name[:80])
    return tuple(p for p in parts if p not in ("", "."))


def extract(archive: Path, dest: Path, strip_top: bool) -> None:
    """Entpackt ein ZIP sicher: kein Zip-Slip, keine Symlinks, Größen- und Dateilimit."""
    dest = dest.resolve()
    try:
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_UNPACKED:
                raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="archive too large")
            entries = []
            for info in infos:
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="symlink")
                parts = _clean_parts(info.filename)
                if parts:
                    entries.append((info, parts))
            strip = 0
            if strip_top and entries and all(len(p) > 1 or i.is_dir() for i, p in entries):
                if len({p[0] for _i, p in entries}) == 1:
                    strip = 1
            written = 0
            for info, parts in entries:
                parts = parts[strip:]
                if not parts:
                    continue
                target = dest.joinpath(*parts).resolve()
                if target != dest and dest not in target.parents:
                    raise ClaudiosError(E.UNSAFE_ARCHIVE, reason=info.filename[:80])
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as out:
                    while chunk := src.read(65536):
                        written += len(chunk)
                        if written > MAX_UNPACKED:
                            raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="archive too large")
                        out.write(chunk)
    except zipfile.BadZipFile:
        raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="corrupt archive") from None


# ---------------------------------------------------------------- Installation


def install(comp: Component, *, root: Path | None = None, client: httpx.Client | None = None,
            progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    target = (root or paths.tools_dir()) / comp.name
    try:
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp_name:
            tmp = Path(tmp_name)
            archive = tmp / "download.bin"
            download(comp, archive, client=client, progress=progress, cancel=cancel)
            stage = tmp / "stage"
            stage.mkdir()
            report(comp.name, "extract", 0, 1)
            if comp.kind == "archive":
                extract(archive, stage, comp.strip_top)
            else:
                shutil.copy2(archive, stage / comp.filename)
            if find_exe(comp, stage) is None:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"{comp.name}: {comp.exe} not found")
            (stage / MARKER).write_text(json.dumps({
                "version": comp.version, "sha256": comp.sha256,
                "installed": datetime.now(UTC).isoformat(timespec="seconds"),
            }), "utf-8")
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(stage), str(target))
            report(comp.name, "extract", 1, 1)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None


# ---------------------------------------------------------------- Entfernen


@dataclass(frozen=True)
class UninstallItem:
    key: str        # "tool:<name>" oder cache | logs | config | reports
    kind: str       # tool | category
    title: str
    size: int
    default: bool


def dir_size(path: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            file = Path(dirpath) / name
            try:
                if not file.is_symlink():
                    total += file.stat().st_size
            except OSError:
                pass
    return total


def _log_files() -> list[Path]:
    return [p for p in paths.logs_dir().glob("claudios.log*") if p.is_file()]


def uninstall_items(lock: list[Component] | None = None, root: Path | None = None) -> list[UninstallItem]:
    comps = load_lock() if lock is None else lock
    tools = root or paths.tools_dir()
    items = []
    for comp in comps:
        folder = tools / comp.name
        if folder.is_dir():
            items.append(UninstallItem(f"tool:{comp.name}", "tool", comp.title, dir_size(folder), True))
    cache = dir_size(paths.cache_dir())
    if cache:
        items.append(UninstallItem("cache", "category", "cache", cache, True))
    logs = sum(f.stat().st_size for f in _log_files())
    if logs:
        items.append(UninstallItem("logs", "category", "logs", logs, True))
    config = dir_size(paths.config_dir())
    if config:
        items.append(UninstallItem("config", "category", "config", config, False))
    reports = paths.reports_dir()
    if reports.is_dir() and dir_size(reports):
        items.append(UninstallItem("reports", "category", "reports", dir_size(reports), False))
    return items


def dependents(names: list[str], lock: list[Component] | None = None, *,
               installed_only: bool = True, root: Path | None = None) -> list[str]:
    """Komponenten, die (auch indirekt) von den entfernten abhängen."""
    comps = load_lock() if lock is None else lock
    closure = set(names)
    changed = True
    while changed:
        changed = False
        for comp in comps:
            if comp.name not in closure and closure & set(comp.depends):
                closure.add(comp.name)
                changed = True
    tools = root or paths.tools_dir()
    return [c.name for c in comps if c.name in closure and c.name not in names
            and (not installed_only or (tools / c.name).is_dir())]


def affected_checks(names: list[str], lock: list[Component] | None = None) -> int:
    """Anzahl der Prüfungen, die wegen der entfernten Komponenten (und ihrer Abhängigen) nicht mehr laufen."""
    from ..checks import load_all
    from ..core.registry import REGISTRY

    load_all()
    gone = set(names) | set(dependents(names, lock, installed_only=False))
    return sum(1 for rc in REGISTRY.values() if gone & set(rc.meta.needs))


def _remove_dir(path: Path, base: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    real = path.resolve()
    if base.resolve() not in real.parents:
        raise OSError("outside of base folder")
    shutil.rmtree(real)


def uninstall(keys: list[str], lock: list[Component] | None = None,
              root: Path | None = None) -> dict[str, str | None]:
    """Entfernt nur bekannte Ziele. Gibt je Schlüssel None (ok) oder den Fehlernamen zurück."""
    comps = {c.name for c in (load_lock() if lock is None else lock)}
    tools = root or paths.tools_dir()
    result: dict[str, str | None] = {}
    for key in keys:
        try:
            if key.startswith("tool:") and key[5:] in comps:
                folder = tools / key[5:]
                if folder.exists():
                    _remove_dir(folder, tools)
            elif key == "cache":
                _remove_dir(paths.cache_dir(), paths.data_dir())
            elif key == "logs":
                for file in _log_files():
                    file.unlink()
            elif key == "config":
                _remove_dir(paths.config_dir(), paths.data_dir())
            elif key == "reports":
                reports = paths.reports_dir()
                if reports.exists():
                    _remove_dir(reports, reports.parent)
            else:
                result[key] = "unknown"
                continue
            result[key] = None
        except OSError as exc:
            result[key] = type(exc).__name__
    return result"""Komponenten-Manager: Download nur per HTTPS mit SHA256-Prüfung, sicheres Entpacken, Installation, Entfernen.
Ungeprüfte Komponenten (ohne Prüfsumme in der Lock-Datei) werden nie installiert."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin

import httpx

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from .lock import Component, load_lock

MAX_DOWNLOAD = 700 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
MAX_FILES = 50_000
MARKER = ".claudios-installed.json"
_REDIRECTS = {301, 302, 303, 307, 308}
Progress = Callable[[str, str, int, int], None]


# ---------------------------------------------------------------- Status


def find_exe(comp: Component, base: Path) -> Path | None:
    return next(iter(base.glob(comp.exe)), None)


def status(comp: Component, root: Path | None = None) -> str:
    """installed | missing | outdated | not_pinned"""
    if not comp.sha256:
        return "not_pinned"
    base = (root or paths.tools_dir()) / comp.name
    try:
        info = json.loads((base / MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return "missing"
    if find_exe(comp, base) is None:
        return "missing"
    if info.get("sha256") != comp.sha256 or info.get("version") != comp.version:
        return "outdated"
    return "installed"


def component_checker(root: Path | None = None, lock: list[Component] | None = None) -> Callable[[str], bool]:
    comps = {c.name: c for c in (load_lock() if lock is None else lock)}

    def available(name: str) -> bool:
        comp = comps.get(name)
        return comp is not None and status(comp, root) == "installed"

    return available


def tool_path(name: str, lock: list[Component] | None = None, root: Path | None = None) -> Path | None:
    comps = {c.name: c for c in (load_lock() if lock is None else lock)}
    comp = comps.get(name)
    if comp is None:
        return None
    return find_exe(comp, (root or paths.tools_dir()) / name)


# ---------------------------------------------------------------- Download


def _content_length(value: str | None, fallback: int) -> int:
    try:
        return int(value) if value else fallback
    except ValueError:
        return fallback


def download(comp: Component, dest: Path, *, client: httpx.Client | None = None,
             progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
    if not comp.sha256:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)
    if not comp.url.startswith("https://"):
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="HTTPS required")
    report = progress or (lambda *_: None)
    own = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=False, trust_env=False)
    digest = hashlib.sha256()
    url = comp.url
    try:
        for _hop in range(6):
            with http.stream("GET", url) as resp:
                if resp.status_code in _REDIRECTS:
                    url = urljoin(url, resp.headers.get("location", ""))
                    if not url.startswith("https://"):
                        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="redirect without HTTPS")
                    continue
                if resp.status_code != 200:
                    raise ClaudiosError(E.DOWNLOAD_FAILED, reason=f"HTTP {resp.status_code}")
                total = _content_length(resp.headers.get("content-length"), comp.size)
                if total > MAX_DOWNLOAD:
                    raise ClaudiosError(E.DOWNLOAD_FAILED, reason="file too large")
                done = 0
                with dest.open("wb") as out:
                    for chunk in resp.iter_bytes(65536):
                        if cancel is not None and cancel.is_set():
                            raise ClaudiosError(E.INSTALL_CANCELLED)
                        done += len(chunk)
                        if done > MAX_DOWNLOAD:
                            raise ClaudiosError(E.DOWNLOAD_FAILED, reason="file too large")
                        digest.update(chunk)
                        out.write(chunk)
                        report(comp.name, "download", done, total)
                break
        else:
            raise ClaudiosError(E.DOWNLOAD_FAILED, reason="too many redirects")
    except httpx.HTTPError as exc:
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason=type(exc).__name__) from None
    finally:
        if own:
            http.close()
    report(comp.name, "verify", 1, 1)
    if digest.hexdigest() != comp.sha256.lower():
        dest.unlink(missing_ok=True)
        raise ClaudiosError(E.CHECKSUM_MISMATCH, reason=comp.name)


# ---------------------------------------------------------------- Entpacken


def _clean_parts(name: str) -> tuple[str, ...]:
    norm = name.replace("\\", "/")
    parts = PurePosixPath(norm).parts
    if norm.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
        raise ClaudiosError(E.UNSAFE_ARCHIVE, reason=name[:80])
    return tuple(p for p in parts if p not in ("", "."))


def extract(archive: Path, dest: Path, strip_top: bool) -> None:
    """Entpackt ein ZIP sicher: kein Zip-Slip, keine Symlinks, Größen- und Dateilimit."""
    dest = dest.resolve()
    try:
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_UNPACKED:
                raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="archive too large")
            entries = []
            for info in infos:
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="symlink")
                parts = _clean_parts(info.filename)
                if parts:
                    entries.append((info, parts))
            strip = 0
            if strip_top and entries and all(len(p) > 1 or i.is_dir() for i, p in entries):
                if len({p[0] for _i, p in entries}) == 1:
                    strip = 1
            written = 0
            for info, parts in entries:
                parts = parts[strip:]
                if not parts:
                    continue
                target = dest.joinpath(*parts).resolve()
                if target != dest and dest not in target.parents:
                    raise ClaudiosError(E.UNSAFE_ARCHIVE, reason=info.filename[:80])
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as out:
                    while chunk := src.read(65536):
                        written += len(chunk)
                        if written > MAX_UNPACKED:
                            raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="archive too large")
                        out.write(chunk)
    except zipfile.BadZipFile:
        raise ClaudiosError(E.UNSAFE_ARCHIVE, reason="corrupt archive") from None


# ---------------------------------------------------------------- Installation


def install(comp: Component, *, root: Path | None = None, client: httpx.Client | None = None,
            progress: Progress | None = None, cancel: threading.Event | None = None) -> None:
    report = progress or (lambda *_: None)
    target = (root or paths.tools_dir()) / comp.name
    try:
        with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp_name:
            tmp = Path(tmp_name)
            archive = tmp / "download.bin"
            download(comp, archive, client=client, progress=progress, cancel=cancel)
            stage = tmp / "stage"
            stage.mkdir()
            report(comp.name, "extract", 0, 1)
            if comp.kind == "archive":
                extract(archive, stage, comp.strip_top)
            else:
                shutil.copy2(archive, stage / comp.filename)
            if find_exe(comp, stage) is None:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"{comp.name}: {comp.exe} not found")
            (stage / MARKER).write_text(json.dumps({
                "version": comp.version, "sha256": comp.sha256,
                "installed": datetime.now(UTC).isoformat(timespec="seconds"),
            }), "utf-8")
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(stage), str(target))
            report(comp.name, "extract", 1, 1)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None


# ---------------------------------------------------------------- Entfernen


@dataclass(frozen=True)
class UninstallItem:
    key: str        # "tool:<name>" oder cache | logs | config | reports
    kind: str       # tool | category
    title: str
    size: int
    default: bool


def dir_size(path: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            file = Path(dirpath) / name
            try:
                if not file.is_symlink():
                    total += file.stat().st_size
            except OSError:
                pass
    return total


def _log_files() -> list[Path]:
    return [p for p in paths.logs_dir().glob("claudios.log*") if p.is_file()]


def uninstall_items(lock: list[Component] | None = None, root: Path | None = None) -> list[UninstallItem]:
    comps = load_lock() if lock is None else lock
    tools = root or paths.tools_dir()
    items = []
    for comp in comps:
        folder = tools / comp.name
        if folder.is_dir():
            items.append(UninstallItem(f"tool:{comp.name}", "tool", comp.title, dir_size(folder), True))
    cache = dir_size(paths.cache_dir())
    if cache:
        items.append(UninstallItem("cache", "category", "cache", cache, True))
    logs = sum(f.stat().st_size for f in _log_files())
    if logs:
        items.append(UninstallItem("logs", "category", "logs", logs, True))
    config = dir_size(paths.config_dir())
    if config:
        items.append(UninstallItem("config", "category", "config", config, False))
    reports = paths.reports_dir()
    if reports.is_dir() and dir_size(reports):
        items.append(UninstallItem("reports", "category", "reports", dir_size(reports), False))
    return items


def dependents(names: list[str], lock: list[Component] | None = None, *,
               installed_only: bool = True, root: Path | None = None) -> list[str]:
    """Komponenten, die (auch indirekt) von den entfernten abhängen."""
    comps = load_lock() if lock is None else lock
    closure = set(names)
    changed = True
    while changed:
        changed = False
        for comp in comps:
            if comp.name not in closure and closure & set(comp.depends):
                closure.add(comp.name)
                changed = True
    tools = root or paths.tools_dir()
    return [c.name for c in comps if c.name in closure and c.name not in names
            and (not installed_only or (tools / c.name).is_dir())]


def affected_checks(names: list[str], lock: list[Component] | None = None) -> int:
    """Anzahl der Prüfungen, die wegen der entfernten Komponenten (und ihrer Abhängigen) nicht mehr laufen."""
    from ..checks import load_all
    from ..core.registry import REGISTRY

    load_all()
    gone = set(names) | set(dependents(names, lock, installed_only=False))
    return sum(1 for rc in REGISTRY.values() if gone & set(rc.meta.needs))


def _remove_dir(path: Path, base: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    real = path.resolve()
    if base.resolve() not in real.parents:
        raise OSError("outside of base folder")
    shutil.rmtree(real)


def uninstall(keys: list[str], lock: list[Component] | None = None,
              root: Path | None = None) -> dict[str, str | None]:
    """Entfernt nur bekannte Ziele. Gibt je Schlüssel None (ok) oder den Fehlernamen zurück."""
    comps = {c.name for c in (load_lock() if lock is None else lock)}
    tools = root or paths.tools_dir()
    result: dict[str, str | None] = {}
    for key in keys:
        try:
            if key.startswith("tool:") and key[5:] in comps:
                folder = tools / key[5:]
                if folder.exists():
                    _remove_dir(folder, tools)
            elif key == "cache":
                _remove_dir(paths.cache_dir(), paths.data_dir())
            elif key == "logs":
                for file in _log_files():
                    file.unlink()
            elif key == "config":
                _remove_dir(paths.config_dir(), paths.data_dir())
            elif key == "reports":
                reports = paths.reports_dir()
                if reports.exists():
                    _remove_dir(reports, reports.parent)
            else:
                result[key] = "unknown"
                continue
            result[key] = None
        except OSError as exc:
            result[key] = type(exc).__name__
    return result