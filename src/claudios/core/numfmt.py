"""Einzige erlaubte Stelle für Zahlenausgaben in UI und Berichten (nicht für JSON-Werte)."""
from __future__ import annotations


def format_number(value: float, lang: str = "de", decimals: int = 0) -> str:
    if lang not in ("de", "en"):
        raise ValueError("lang must be 'de' or 'en'")
    rounded = round(float(value), decimals)
    text = f"{abs(rounded):,.{decimals}f}"  # englisches Grundformat: 1,234.5
    if lang == "de":
        text = text.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return ("-" if rounded < 0 else "") + text


def format_bytes(num: int, lang: str = "de") -> str:
    size = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{format_number(size, lang, 0 if unit == 'B' else 1)} {unit}"
        size /= 1024
    raise AssertionError  # pragma: no cover
