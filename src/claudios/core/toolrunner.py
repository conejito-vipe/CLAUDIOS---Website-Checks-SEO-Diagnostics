"""Startet externe Prüfwerkzeuge: nie über eine Shell, mit Argumentliste, Zeit- und Ausgabelimit,
bereinigter Umgebung. Das Programm muss im Werkzeugordner liegen.
Im Scan gelten für Browser, ZAP und sslyze ein Gesamtbudget und eine Mindestpause (core/toolbudget.py)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .. import paths
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS
from .toolbudget import acquire, release

_KEEP_ENV = ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT")


@dataclass(frozen=True)
class ToolResult:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool


def ensure_in_tools(program: Path | str, root: Path | None = None) -> None:
    """Verhindert, dass beliebige Programme gestartet werden (kein Auflösen von Symlinks, nur Pfadvergleich)."""
    base = Path(os.path.abspath(root or paths.tools_dir()))
    target = Path(os.path.abspath(program))
    if base not in target.parents:
        raise ClaudiosError(E.TOOL_FAILED, reason="program outside of the tools folder")


def _env(extra: dict[str, str] | None) -> dict[str, str]:
    env = {key: os.environ[key] for key in _KEEP_ENV if key in os.environ}
    env.update(extra or {})
    return env


def _decode(data: bytes, limit: int) -> tuple[str, bool]:
    return data[:limit].decode("utf-8", errors="replace"), len(data) > limit


def run_tool(args: list, *, cwd: Path | str, timeout: float | None = None, root: Path | None = None,
             extra_env: dict[str, str] | None = None) -> ToolResult:
    ensure_in_tools(args[0], root)
    slot = acquire(args)  # nur im Scan und nur für Browser, ZAP, sslyze: Gesamtbudget und Mindestpause
    wanted = timeout or LIMITS.tool_timeout_seconds
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [str(a) for a in args], cwd=str(cwd), env=_env(extra_env), capture_output=True,
            timeout=slot.cap(wanted) if slot else wanted, shell=False, creationflags=flags, check=False)
    except subprocess.TimeoutExpired:
        raise ClaudiosError(E.TOOL_FAILED, reason="timeout") from None
    except OSError as exc:
        raise ClaudiosError(E.TOOL_FAILED, reason=type(exc).__name__) from None
    finally:
        release(slot)
    out, cut_out = _decode(proc.stdout, LIMITS.tool_output_max)
    err, cut_err = _decode(proc.stderr, LIMITS.tool_output_max)
    return ToolResult(proc.returncode, out, err, cut_out or cut_err)
