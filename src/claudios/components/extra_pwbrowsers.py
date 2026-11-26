"""Komponente Firefox und WebKit (Playwright) für die Browser-Gegenprobe im Profil Tief. Wird automatisch gefunden."""
from .lock import Component

COMPONENT = Component(
    name="pw-browsers", title="Firefox und WebKit (Playwright)", kind="pwbrowsers", version="", url="", sha256="",
    size=0, license="MPL-2.0 (Firefox), LGPL-2.1 und BSD (WebKit), bitte prüfen", source="https://playwright.dev/",
    depends=("playwright",), exe=".claudios-installed.json", filename="", strip_top=False,
    platforms=("windows", "macos"))
