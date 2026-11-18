"""Gemeinsame Hilfen für die Schema.org-Prüfungen: JSON-LD einlesen und Typen vergleichen."""
from __future__ import annotations

import json
import re

_LD = re.compile(r"^application/ld\+json$", re.I)
MAX_BLOCK = 200_000
LOCAL_TYPES = frozenset({
    "localbusiness", "restaurant", "store", "dentist", "physician", "hotel", "barorpub", "cafeorcoffeeshop", "autorepair",
    "beautysalon", "hairsalon", "gym", "healthclub", "legalservice", "realestateagent", "lodgingbusiness",
    "foodestablishment", "medicalbusiness", "professionalservice", "financialservice", "homeandconstructionbusiness",
    "automotivebusiness", "entertainmentbusiness"})
ARTICLE_TYPES = frozenset({"article", "newsarticle", "blogposting", "techarticle", "scholarlyarticle"})


def _name(value: str) -> str:
    text = value.strip().lower()
    return text.rsplit("/", 1)[-1].rsplit(":", 1)[-1].rsplit("#", 1)[-1]


def types_of(item: dict) -> set[str]:
    raw = item.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return {_name(v) for v in values if isinstance(v, str) and v.strip()}


def _flatten(data, depth: int = 0) -> list[dict]:
    if depth > 4:
        return []
    out: list[dict] = []
    if isinstance(data, list):
        for entry in data[:200]:
            out.extend(_flatten(entry, depth + 1))
    elif isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for entry in graph[:200]:
                out.extend(_flatten(entry, depth + 1))
        if data.get("@type"):
            out.append(data)
    return out


def items(pg) -> list[dict]:
    """Alle JSON-LD-Objekte mit @type einer Seite (auch aus @graph), höchstens 300."""
    out: list[dict] = []
    for block in pg.soup.find_all("script", attrs={"type": _LD}, limit=30):
        raw = block.string or block.get_text()
        if not raw or len(raw) > MAX_BLOCK:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        out.extend(_flatten(data))
    return out[:300]


def has(item: dict, prop: str) -> bool:
    return item.get(prop) not in (None, "", [], {})


def first_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                return entry
    return {}
