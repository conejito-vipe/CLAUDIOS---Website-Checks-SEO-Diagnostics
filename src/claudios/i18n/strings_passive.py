"""UI-Text für die Zusatz-Probe (security.txt, Favicon, MTA-STS, Fingerprints)."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({"probe.passive": "Zusatzdateien (security.txt, Favicon, MTA-STS)"})
TEXTS["en"].update({"probe.passive": "Extra files (security.txt, favicon, MTA-STS)"})
