from __future__ import annotations

import importlib

_MODULES = ("system", "html_checks", "security", "seo", "dns", "links", "takeover", "ads", "hardening")
_loaded = False


def load_all() -> None:
    global _loaded
    if not _loaded:
        for name in _MODULES:
            importlib.import_module(f"{__name__}.{name}")
        _loaded = True