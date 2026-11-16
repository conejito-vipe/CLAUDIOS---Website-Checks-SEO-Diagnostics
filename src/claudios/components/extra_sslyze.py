"""Komponente sslyze (TLS-Analyse): eigene Python-Umgebung, wird nur als externer Prozess aufgerufen (AGPL-3.0)."""
from .lock import Component

COMPONENT = Component(
    name="sslyze", title="sslyze (TLS-Analyse, eigene Python-Umgebung)", kind="pip", version="", url="",
    sha256="", size=0, license="AGPL-3.0 (nur als separates Programm aufgerufen)",
    source="https://github.com/nabla-c0d3/sslyze", depends=(), exe="Scripts/python.exe", filename="",
    strip_top=False)