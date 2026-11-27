"""Handbuch und Technik-Doku, automatisch aus der Check-Registry erzeugt (kein Qt, daher testbar)."""
from __future__ import annotations

from .checks import load_all
from .core.limits import LIMITS
from .core.numfmt import format_number
from .core.registry import REGISTRY
from .i18n.strings import text

RULE = "-" * 72


def _block(mode: str, lang: str, cid: str, rc) -> str:
    m = rc.meta

    def lab(key: str) -> str:
        return text(lang, key)

    kind = lab("doc.active") if m.kind == "active" else lab("doc.passive")
    lines = [f"{m.title[lang]} [{cid}]"]
    if mode == "tech":
        lines.append(f"{lab('doc.kind')}: {kind} | {lab('doc.profiles')}: {', '.join(m.profiles)}")
        lines.append(f"{lab('doc.method')}: {m.method[lang]}")
        lines.append(f"{lab('doc.logic')}: {m.logic[lang]}")
    lines.append(f"{lab('doc.why')} {m.why[lang]}")
    lines.append(f"{lab('doc.fix')}: {m.fix[lang]}")
    lines.append(f"{lab('doc.refs')}: {', '.join(m.refs)}")
    if mode == "tech":
        code = rc.source_code()
        if code:
            lines.append(f"{lab('doc.code')}:\n{code.rstrip()}")
    return "\n\n".join(lines)  # vor jedem Punkt (Art, Methode, Warum ...) steht eine Leerzeile


def render_doc(mode: str, lang: str, query: str = "") -> str:
    load_all()
    needle = query.strip().lower()
    blocks = []
    for cid, rc in sorted(REGISTRY.items()):
        block = _block(mode, lang, cid, rc)
        if not needle or needle in block.lower():
            blocks.append(block)
    if mode == "tech":
        head = text(lang, "doc.tech_intro")
    else:
        head = text(lang, "doc.intro", depth=format_number(LIMITS.max_depth, lang))
    body = f"\n\n{RULE}\n\n".join(blocks) if blocks else text(lang, "doc.none")
    return f"{head}\n\n{RULE}\n\n{body}\n"
