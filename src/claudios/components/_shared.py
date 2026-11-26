"""Gemeinsame Bausteine der Komponenten-Installer (npm, Playwright, pip): Statusprüfung und Vorbedingungen."""
from __future__ import annotations

import json
import shutil
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from .lock import Component

MARKER = ".claudios-installed.json"


def marker_status(comp: Component, digest: str, root: Path | None = None,
                  extra_present: Callable[[Path], bool] | None = None) -> str:
    """installed | missing | outdated | not_pinned. extra_present prüft weitere Dateien (z. B. heruntergeladene Browser)."""
    if not digest:
        return "not_pinned"
    base = (root or paths.tools_dir()) / comp.name
    try:
        info = json.loads((base / MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return "missing"
    if next(iter(base.glob(comp.exe)), None) is None or (extra_present is not None and not extra_present(base)):
        return "missing"
    return "installed" if info.get("sha256") == digest else "outdated"


def require_pinned(comp: Component, digest: str) -> None:
    if not digest:
        raise ClaudiosError(E.COMPONENT_NOT_PINNED, reason=comp.name)


def require_cancel_free(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.INSTALL_CANCELLED)


def require_npm(node: Path | None) -> Path:
    """Prüft Node.js und npm und gibt den Pfad zu npm-cli.js zurück."""
    if node is None:
        raise ClaudiosError(E.COMPONENT_MISSING, reason="node")
    # Windows: npm liegt neben node.exe; Mac/Linux: bin/node und lib/node_modules/npm
    candidates = (node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
                  node.parent.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js")
    npm_cli = next((c for c in candidates if c.is_file()), candidates[0])
    if not npm_cli.is_file():
        raise ClaudiosError(E.TOOL_FAILED, reason="npm-cli.js not found")
    return npm_cli


def write_marker(folder: Path, comp: Component, digest: str) -> None:
    """Vermerkt Version und Prüfsumme der Sperrdatei: daran erkennt status() eine veraltete Installation."""
    (folder / MARKER).write_text(json.dumps({
        "version": comp.version, "sha256": digest,
        "installed": datetime.now(UTC).isoformat(timespec="seconds"),
    }), "utf-8")


def replace_dir(stage: Path, target: Path) -> None:
    """Ersetzt den Zielordner durch den fertig vorbereiteten (erst wenn alles geklappt hat)."""
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(stage), str(target))
