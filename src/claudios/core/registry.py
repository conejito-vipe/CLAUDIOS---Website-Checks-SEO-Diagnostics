"""Check-Registry. Pflichtfelder inkl. 'warum' in DE und EN: Handbuch und Technik-Doku werden daraus erzeugt."""
from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass

PROFILE_MAP = {"q": "quick", "s": "standard", "d": "deep"}
ID_RE = re.compile(r"^[A-Z]{3}-[A-Z]{3}-\d{3}$")


def _t(value: str | dict) -> dict[str, str]:
    """'Deutscher Text ## English text' -> {'de': ..., 'en': ...}"""
    if isinstance(value, dict):
        return value
    parts = [p.strip() for p in value.split(" ## ")]
    return {"de": parts[0], "en": parts[1] if len(parts) > 1 else ""}


@dataclass(frozen=True)
class CheckMeta:
    id: str
    title: dict
    why: dict
    method: dict
    logic: dict
    fix: dict
    refs: tuple
    profiles: tuple
    kind: str
    source: str
    needs: tuple

    @property
    def category(self) -> str:
        return self.id.split("-")[0]


@dataclass(frozen=True)
class RegisteredCheck:
    meta: CheckMeta
    fn: Callable

    def source_code(self) -> str:
        try:
            return inspect.getsource(self.fn)
        except (OSError, TypeError):
            return ""


REGISTRY: dict[str, RegisteredCheck] = {}


def check(id: str, *, title: str, why: str, method: str, logic: str, fix: str, refs: list[str],
          profiles: str = "qsd", kind: str = "passive", source: str = "local", needs: tuple = ()):
    def deco(fn: Callable) -> Callable:
        if id in REGISTRY:
            raise ValueError(f"duplicate check id {id}")
        meta = CheckMeta(id, _t(title), _t(why), _t(method), _t(logic), _t(fix), tuple(refs),
                         tuple(PROFILE_MAP[c] for c in profiles), kind, source, tuple(needs))
        REGISTRY[id] = RegisteredCheck(meta, fn)
        return fn
    return deco


def validate_registry() -> list[str]:
    errs: list[str] = []
    for cid, rc in REGISTRY.items():
        m = rc.meta
        if not ID_RE.match(cid):
            errs.append(f"{cid}: invalid id format")
        for fld in ("title", "why", "method", "logic", "fix"):
            for lang in ("de", "en"):
                if not getattr(m, fld).get(lang, "").strip():
                    errs.append(f"{cid}: {fld}.{lang} missing")
        if not m.refs or any(not r.startswith("https://") for r in m.refs):
            errs.append(f"{cid}: references missing or not https")
        if m.kind not in ("passive", "active"):
            errs.append(f"{cid}: invalid kind")
    return errs
