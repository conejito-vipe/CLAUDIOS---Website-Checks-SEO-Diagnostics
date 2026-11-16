"""Lock-Datei der Komponenten: feste Versionen mit SHA256. Wird beim Laden streng geprüft."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

_HEX = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[a-z0-9-]+$")
_KINDS = ("archive", "file")


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


def parse_lock(raw: dict) -> list[Component]:
    if raw.get("schema") != 1:
        raise ValueError("unsupported lock schema")
    out: list[Component] = []
    seen: set[str] = set()
    for item in raw.get("components", []):
        comp = Component(
            name=item["name"], title=item["title"], kind=item["kind"], version=item.get("version", ""),
            url=item.get("url", ""), sha256=item.get("sha256", "").lower(), size=int(item.get("size", 0)),
            license=item["license"], source=item["source"], depends=tuple(item.get("depends", [])),
            exe=item["exe"], filename=item.get("filename", ""), strip_top=bool(item.get("strip_top", False)),
        )
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
        seen.add(comp.name)
        out.append(comp)
    return out


def load_lock(path: Path | str | None = None) -> list[Component]:
    if path is None:
        text = resources.files("claudios.components").joinpath("components.lock.json").read_text("utf-8")
    else:
        text = Path(path).read_text("utf-8")
    return parse_lock(json.loads(text))