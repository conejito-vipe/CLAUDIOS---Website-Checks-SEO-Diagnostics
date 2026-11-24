"""Tausendertrenner in Anzeigetexten (Befundmeldungen), je nach Sprache (DE 1.000, EN 1,000).
Nur reine Zahlen ab vier Stellen im Fließtext werden umgeschrieben. Nicht angefasst werden Zahlen, die an Buchstaben,
Punkte, Schrägstriche, Bindestriche oder ein Gleichheitszeichen grenzen (Adressen, Versionen, Kennungen, Quelltext),
Jahreszahlen von 1900 bis 2100 und Zahlen mit führender Null. Eine Zahl mit einem x dahinter (zum Beispiel 2019x) zählt als Anzahl."""
from __future__ import annotations

import re

from .numfmt import format_number

_NUM = re.compile(r"(?<![\w.,:/#=&?@%+\-])(\d{4,})(x\b)?(?![\w/])")


def _replace(lang: str):
    def inner(match: re.Match) -> str:
        digits, suffix = match.group(1), match.group(2) or ""
        if digits.startswith("0"):
            return match.group(0)
        value = int(digits)
        if not suffix and len(digits) == 4 and 1900 <= value <= 2100:
            return match.group(0)
        return format_number(value, lang, 0) + suffix

    return inner


def localize_numbers(text: str, lang: str) -> str:
    return _NUM.sub(_replace(lang), text) if text else text
