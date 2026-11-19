"""Komfort bei der Eingabe der Adresse: Leerzeichen am Rand entfernen und http:// zu https:// machen. Das lockert nichts:
Claudios öffnet weiter nur HTTPS (core/guard.py prüft alles danach noch einmal). Ohne Schema ergänzt guard.py https://."""
from __future__ import annotations

import re

_LOCAL = re.compile(r"^(localhost|127\.\d+\.\d+\.\d+|\[::1\])(:\d+)?$", re.I)


def clean_input(raw: str, allow_localhost: bool = False) -> str:
    text = (raw or "").strip()
    if text.lower().startswith("http://"):
        rest = text[7:]
        host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
        if not (allow_localhost and _LOCAL.match(host)):
            return "https://" + rest
    return text
