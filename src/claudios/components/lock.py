"""Lock-Datei der Komponenten: feste Versionen mit SHA256. Wird beim Laden streng geprüft.
Weitere Komponenten kommen als neue Datei components/extra_*.py (Konstante COMPONENT), ohne Änderung hier."""
from __future__ import annotations

import importlib
import json
import os
import pkgutil
import re
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_HEX = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z0-9-]+$")
_KINDS = ("archive", "file", "npm", "pip")
_SELF_PINNED = ("npm", "pip")  # werden über ihre eigene Sperrdatei geprüft, nicht über url/sha256


@dataclass(frozen=True)
class Component:
    name: str
    title: str
    kind: str
    version: str
    url: str
    sha256: str
    size: int
    license: str
    source: str
    depends: tuple[str, ...]
    exe: str
    filename: str
    strip_top: bool
    platforms: tuple[str, ...] = ("windows",)  # auf welchen Systemen die Komponente eingerichtet werden kann


def host_platform() -> str:
    """"macos" auf dem Mac, sonst "windows" (Linux dient nur der Entwicklung und den Tests und nutzt die Windows-Sperrdatei)."""
    forced = os.environ.get("CLAUDIOS_PLATFORM")  # nur für Tests und Fehlersuche
    if forced in ("windows", "macos"):
        return forced
    return "macos" if sys.platform == "darwin" else "windows"


def supported_here(comps: list[Component]) -> list[Component]:
    return [c for c in comps if host_platform() in c.platforms]


# Fest im Code: Die Prüfsumme ist die der mitgelieferten package-lock.json (npm prüft damit jedes Paket).
NPM_TOOLS = Component(
    name="npm-tools", title="ESLint, Stylelint, retire.js (npm)", kind="npm", version="", url="", sha256="",
    size=0, license="MIT / Apache-2.0 (bitte prüfen)", source="https://www.npmjs.com/", depends=("node",),
    exe="node_modules/eslint/bin/eslint.js", filename="", strip_top=False, platforms=("windows", "macos"))


_VARIANT_KEYS = ("version", "url", "sha256", "size", "exe", "strip_top")


def _for_platform(item: dict, platform: str) -> dict:
    """Eintrag für das System: 'variants' enthält abweichende Adresse, Prüfsumme und Programmpfad je System (macos)."""
    variants = item.get("variants") or {}
    if not isinstance(variants, dict) or any(k not in ("macos",) for k in variants):
        raise ValueError(f"{item.get('name')}: invalid variants")
    merged = dict(item)
    if platform in variants:
        extra = variants[platform]
        types = {"version": str, "url": str, "sha256": str, "size": int, "exe": str, "strip_top": bool}
        if (not isinstance(extra, dict) or any(k not in _VARIANT_KEYS for k in extra) or not extra.get("sha256")
                or any(not isinstance(v, types[k]) or (k == "size" and isinstance(v, bool)) for k, v in extra.items())):
            raise ValueError(f"{item.get('name')}: invalid variant")
        merged.update(extra)
    merged["platforms"] = list(dict.fromkeys([*item.get("platforms", ["windows"]), *variants]))
    return merged


def parse_lock(raw: dict, platform: str | None = None) -> list[Component]:
    if raw.get("schema") != 1:
        raise ValueError("unsupported lock schema")
    out: list[Component] = []
    seen: set[str] = set()
    for item in (_for_platform(i, platform or host_platform()) for i in raw.get("components", [])):
        comp = Component(
            name=item["name"], title=item["title"], kind=item["kind"], version=item.get("version", ""),
            url=item.get("url", ""), sha256=item.get("sha256", "").lower(), size=int(item.get("size", 0)),
            license=item["license"], source=item["source"], depends=tuple(item.get("depends", [])),
            exe=item["exe"], filename=item.get("filename", ""), strip_top=bool(item.get("strip_top", False)),
            platforms=tuple(item.get("platforms", ["windows"])),
        )
        if not comp.platforms or any(p not in ("windows", "macos") for p in comp.platforms):
            raise ValueError(f"{comp.name}: invalid platforms")
        if not _NAME.match(comp.name) or comp.name in seen:
            raise ValueError(f"invalid or duplicate component name: {comp.name}")
        if comp.kind not in _KINDS:
            raise ValueError(f"{comp.name}: invalid kind")
        if any(dep not in seen for dep in comp.depends):
            raise ValueError(f"{comp.name}: dependency missing or listed later")
        if comp.url and not comp.url.startswith("https://"):
            raise ValueError(f"{comp.name}: url must use https")
        if comp.sha256 and not _HEX.match(comp.sha256):
            raise ValueError(f"{comp.name}: invalid sha256")
        if comp.sha256 and not comp.url:
            raise ValueError(f"{comp.name}: sha256 without url")
        if comp.kind == "file" and (not comp.filename or "/" in comp.filename or "\\" in comp.filename):
            raise ValueError(f"{comp.name}: invalid filename")
        if comp.kind in _SELF_PINNED and (comp.url or comp.sha256):
            raise ValueError(f"{comp.name}: {comp.kind} components are pinned by their own lock file")
        seen.add(comp.name)
        out.append(comp)
    return out


def _extras(seen: set[str]) -> list[Component]:
    """Komponenten aus Dateien components/extra_*.py (Konstante COMPONENT)."""
    out: list[Component] = []
    for info in sorted(pkgutil.iter_modules([str(Path(__file__).parent)]), key=lambda i: i.name):
        if not info.name.startswith("extra_"):
            continue
        comp = getattr(importlib.import_module(f"{__package__}.{info.name}"), "COMPONENT", None)
        if isinstance(comp, Component) and comp.name not in seen and all(d in seen for d in comp.depends):
            out.append(comp)
            seen.add(comp.name)
    return out


def load_lock(path: Path | str | None = None) -> list[Component]:
    if path is not None:
        return parse_lock(json.loads(Path(path).read_text("utf-8")))
    text = resources.files("claudios.components").joinpath("components.lock.json").read_text("utf-8")
    comps = parse_lock(json.loads(text))
    seen = {c.name for c in comps}
    comps.extend(_extras(seen))
    if NPM_TOOLS.name not in seen:
        comps.append(NPM_TOOLS)
    return supported_here(comps)
