"""Anzeigedaten für die Komponenten-Seite: Versionen (aus den Sperrdateien und den installierten Browsern), Download-Größe
und der tatsächlich belegte Platz. Download-Größen ohne Eintrag in der Sperrliste sind SCHÄTZWERTE (ESTIMATES, aus dem
Gedächtnis, ungeprüft) und werden als „ca." angezeigt."""
from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

from .. import paths
from .lock import Component
from .manager import dir_size

MB = 1024 * 1024
ESTIMATES = {"npm-tools": 40 * MB, "playwright": 280 * MB, "pw-browsers": 180 * MB, "sslyze": 20 * MB}
NPM_TOOLS = (("eslint", "ESLint"), ("stylelint", "Stylelint"), ("retire", "retire.js"))
PW_TOOLS = (("playwright", "Playwright"), ("axe-core", "axe-core"), ("@axe-core/playwright", "axe-core/playwright"))


def _read_text(*parts: str) -> str:
    try:
        node = resources.files("claudios.components")
        for part in parts:
            node = node.joinpath(part)
        return node.read_text("utf-8")
    except (OSError, ModuleNotFoundError, FileNotFoundError):
        return ""


def _lock_versions(parts: tuple[str, ...], names) -> list[str]:
    try:
        data = json.loads(_read_text(*parts))
    except ValueError:
        return []
    packages = data.get("packages") if isinstance(data, dict) else None
    if not isinstance(packages, dict):
        return []
    out = []
    for key, label in names:
        entry = packages.get(f"node_modules/{key}")
        version = entry.get("version") if isinstance(entry, dict) else None
        if isinstance(version, str) and version:
            out.append(f"{label} {version}")
    return out


def _browser_versions(root: Path | None) -> dict[str, str]:
    path = (root or paths.tools_dir()) / "playwright" / "node_modules" / "playwright-core" / "browsers.json"
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for item in data.get("browsers", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("name"):
            version = item.get("browserVersion") or (f"r{item['revision']}" if item.get("revision") else "")
            if version:
                out[str(item["name"])] = str(version)
    return out


def sslyze_version() -> str:
    try:
        version = str(json.loads(_read_text("sslyze-wheel.json")).get("version", ""))
    except (ValueError, AttributeError):
        version = ""
    if version:
        return version
    try:
        text = json.loads(_read_text("pip-sslyze.json")).get("requirements", "")
    except (ValueError, AttributeError):
        return ""
    match = re.search(r"^sslyze==([^\s\\]+)", text, re.M)
    return match.group(1) if match else ""


def version_of(comp: Component, root: Path | None = None) -> str:
    if comp.version:
        return comp.version
    parts: list[str] = []
    if comp.name == "npm-tools":
        parts = _lock_versions(("npm", "package-lock.json"), NPM_TOOLS)
    elif comp.name == "playwright":
        parts = _lock_versions(("npm", "pw-package-lock.json"), PW_TOOLS)
        chromium = _browser_versions(root).get("chromium")
        if chromium:
            parts.append(f"Chromium {chromium}")
    elif comp.name == "pw-browsers":
        found = _browser_versions(root)
        parts = [f"{label} {found[key]}" for key, label in (("firefox", "Firefox"), ("webkit", "WebKit")) if found.get(key)]
        if not parts:
            parts = _lock_versions(("npm", "pw-package-lock.json"), (("playwright", "Playwright"),))
    elif comp.name == "sslyze":
        version = sslyze_version()
        parts = [version] if version else []
    return ", ".join(parts)


def download_size_of(comp: Component) -> tuple[int, bool]:
    """(Bytes, geschätzt?). Echte Größen stehen nur in der Sperrliste der Archive und Dateien."""
    if comp.size:
        return comp.size, False
    estimate = ESTIMATES.get(comp.name, 0)
    return estimate, bool(estimate)


def _browser_dirs(tools: Path) -> list[Path]:
    base = tools / "playwright" / "browsers"
    if not base.is_dir():
        return []
    return [p for p in base.iterdir() if p.name.startswith(("firefox", "webkit"))]


def disk_size(comp: Component, root: Path | None = None) -> int:
    """Tatsächlich belegter Platz (entpackt). Firefox und WebKit liegen im Ordner von Playwright und werden getrennt gezählt."""
    tools = root or paths.tools_dir()
    if comp.name == "pw-browsers":
        return sum(dir_size(p) for p in _browser_dirs(tools))
    folder = tools / comp.name
    total = dir_size(folder) if folder.is_dir() else 0
    if comp.name == "playwright":
        total -= sum(dir_size(p) for p in _browser_dirs(tools))
    return max(0, total)
