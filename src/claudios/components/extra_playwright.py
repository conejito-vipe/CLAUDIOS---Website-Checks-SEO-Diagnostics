"""Komponente Playwright (Chromium) und axe-core für die Browser-Prüfungen. Wird beim Start automatisch gefunden."""
from .lock import Component

COMPONENT = Component(
    name="playwright", title="Playwright (Chromium) und axe-core", kind="playwright", version="", url="",
    sha256="", size=0, license="Apache-2.0 (Playwright), MPL-2.0 (axe-core), BSD-3-Clause und weitere (Chromium)",
    source="https://playwright.dev/", depends=("node",), exe="node_modules/playwright/cli.js", filename="",
    strip_top=False)
