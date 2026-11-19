"""Komponente sslyze (TLS-Analyse): eigene Python-Umgebung, wird nur als externer Prozess aufgerufen (AGPL-3.0).
Mit eigenem Python (Entwicklung, CI) liegt sie in einer venv (Art pip). Im gebauten Windows-Programm gibt es kein
Python: dort wird sie in eine Kopie der mitgelieferten Python-Laufzeit installiert (Art pipembed)."""
from __future__ import annotations

from ._runtimelock import frozen
from .lock import Component


def build(is_frozen: bool) -> Component:
    return Component(
        name="sslyze", title="sslyze (TLS-Analyse, eigene Python-Umgebung)",
        kind="pipembed" if is_frozen else "pip", version="", url="", sha256="", size=0,
        license="AGPL-3.0 (nur als separates Programm aufgerufen)",
        source="https://github.com/nabla-c0d3/sslyze",
        depends=("python-runtime", "pip-wheel") if is_frozen else (),
        exe="python.exe" if is_frozen else "Scripts/python.exe", filename="", strip_top=False)


COMPONENT = build(frozen())
