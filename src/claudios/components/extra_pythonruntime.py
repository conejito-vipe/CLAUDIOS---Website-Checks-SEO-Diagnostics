"""Komponente Python-Laufzeit (embeddable). Gibt es nur im gebauten Windows-Programm, das kein eigenes Python hat; sonst
bleibt COMPONENT leer und der Lader ignoriert die Datei. Adresse und Prüfsumme stehen in runtime-lock.json."""
from __future__ import annotations

from ._runtimelock import entry, frozen
from .lock import Component, host_platform


def build(is_frozen: bool) -> Component | None:
    if not is_frozen:
        return None
    if host_platform() == "macos":  # vollständiges Python (python-build-standalone) mit pip, Archiv tar.gz
        pin = entry("python_macos")
        return Component(
            name="python-runtime", title="Python-Laufzeit (für sslyze)", kind="archive", version=pin.get("version", ""),
            url=pin.get("url", ""), sha256=pin.get("sha256", ""), size=pin.get("size", 0),
            license="PSF-2.0 (Python)", source="https://github.com/astral-sh/python-build-standalone",
            depends=(), exe="bin/python3", filename="", strip_top=True, platforms=("macos",))
    pin = entry("python")
    return Component(
        name="python-runtime", title="Python-Laufzeit (für sslyze)", kind="archive", version=pin.get("version", ""),
        url=pin.get("url", ""), sha256=pin.get("sha256", ""), size=pin.get("size", 0),
        license="PSF-2.0 (Python)", source="https://www.python.org/", depends=(), exe="python.exe",
        filename="", strip_top=False)


COMPONENT = build(frozen())
