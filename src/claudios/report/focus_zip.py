"""ZIP für Claude mit Schwerpunkt-Prompt. Wie build_zip in report.py, aber mit dem Prompt des Schwerpunkts und einer
summary.md, die nur dessen Befunde zeigt. report.json und report.html bleiben vollständig."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.limits import LIMITS
from ..core.redact import find_leaks
from . import shots
from .prompts import PREFIXES, prompt_for
from .report import build_report, render_html, render_summary


def focus_report(rep: dict, focus: str) -> dict:
    prefixes = PREFIXES[focus]
    if not prefixes:
        return rep
    return {**rep, "findings": [g for g in rep["findings"] if g["check_id"].startswith(prefixes)]}


def _files(result, lang: str, focus: str) -> dict[str, str]:
    rep = build_report(result, lang)
    files = {"prompt.md": prompt_for(focus, lang),
             "summary.md": render_summary(focus_report(rep, focus), lang),
             "report.json": json.dumps(rep, ensure_ascii=False, indent=2),
             "report.html": render_html(rep, lang)}
    for name, text in files.items():  # letzte Schranke: nichts Erkennbares darf mehr drin sein
        leaks = find_leaks(text)
        if leaks:
            raise ClaudiosError(E.EXPORT_FAILED, reason=f"possible secret in {name}: {leaks[0]}")
    return files


def focus_zip_preview(result, lang: str, focus: str) -> list[tuple[str, int]]:
    return [(name, len(text.encode())) for name, text in _files(result, lang, focus).items()]


def build_focus_zip(result, dest: Path | str, lang: str = "de", focus: str = "general") -> Path:
    dest = Path(dest)
    try:
        files = _files(result, lang, focus)
        manifest = {
            "claudios_version": __version__, "created": datetime.now(UTC).isoformat(), "language": lang,
            "focus": focus,
            "files": {k: {"sha256": hashlib.sha256(v.encode()).hexdigest(), "bytes": len(v.encode())}
                      for k, v in files.items()},
            "limits": asdict(LIMITS), "contains_secrets": False,
        }
        files["manifest.json"] = json.dumps(manifest, indent=2)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, text in files.items():
                archive.writestr(name, text)
            shots.add_to_archive(result, archive)
    except ClaudiosError:
        raise
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return dest
