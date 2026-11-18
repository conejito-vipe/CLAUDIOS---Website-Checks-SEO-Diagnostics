"""Komponente pip-Wheel-Datei (nur im gebauten Windows-Programm). pip startet aus dieser Datei und installiert sslyze in
die Python-Laufzeit. Adresse und Prüfsumme stehen in runtime-lock.json."""
from __future__ import annotations

from ._runtimelock import entry, frozen
from .lock import Component


def build(is_frozen: bool) -> Component | None:
    if not is_frozen:
        return None
    pin = entry("pip")
    return Component(
        name="pip-wheel", title="pip (zum Installieren von sslyze)", kind="file", version=pin.get("version", ""),
        url=pin.get("url", ""), sha256=pin.get("sha256", ""), size=pin.get("size", 0), license="MIT (pip)",
        source="https://pip.pypa.io/", depends=(), exe="pip.whl", filename="pip.whl", strip_top=False)


COMPONENT = build(frozen())
