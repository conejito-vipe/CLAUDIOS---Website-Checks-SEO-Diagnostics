"""Komponente sslyze (TLS-Analyse): eigene Python-Umgebung, wird nur als externer Prozess aufgerufen (AGPL-3.0).
Mit eigenem Python (Entwicklung, CI) liegt sie in einer venv (Art pip). Im gebauten Windows-Programm gibt es kein
Python: dort wird sie in eine Kopie der mitgelieferten Python-Laufzeit installiert (Art pipembed)."""
from __future__ import annotations

from ._runtimelock import frozen
from .lock import Component, host_platform


def build(is_frozen: bool) -> Component:
    mac = host_platform() == "macos"
    if is_frozen:
        depends = ("python-runtime",) if mac else ("python-runtime", "pip-wheel")  # auf dem Mac bringt die Laufzeit pip mit
        exe = "bin/python3" if mac else "python.exe"
    else:
        depends = ()
        exe = "bin/python" if mac else "Scripts/python.exe"
    return Component(
        name="sslyze", title="sslyze (TLS-Analyse, eigene Python-Umgebung)",
        kind="pipembed" if is_frozen else "pip", version="", url="", sha256="", size=0,
        license="AGPL-3.0 (nur als separates Programm aufgerufen)",
        source="https://github.com/nabla-c0d3/sslyze", depends=depends, exe=exe, filename="", strip_top=False,
        platforms=("windows", "macos"))


COMPONENT = build(frozen())
