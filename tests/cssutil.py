"""Hilfsfunktion für Tests: liest ein Qt-Stylesheet in {Selektor: {Eigenschaft: Wert}}, unabhängig von Leerzeichen und
Reihenfolge. So prüfen Tests die Bedeutung einer Regel (Wert einer Eigenschaft) statt eines festen Textstücks."""
from __future__ import annotations

import re

_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def rules(css: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for selectors, body in _RULE.findall(css):
        props = {}
        for declaration in body.split(";"):
            name, _, value = declaration.partition(":")
            if value.strip():
                props[name.strip()] = " ".join(value.split())
        for selector in selectors.split(","):
            out.setdefault(" ".join(selector.split()), {}).update(props)
    return out
