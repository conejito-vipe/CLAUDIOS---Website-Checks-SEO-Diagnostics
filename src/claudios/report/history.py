"""Verlauf: kleine Zusammenfassungen früherer Scans für den Vergleich. Standard ist AUS und wird nur mit dem Schalter
auf der Seite 'Export & Verlauf' gespeichert. Gespeichert werden Prüfung, Schwere, Text, Anzahl und Wertung, nie
Adressen, Belege oder Seiteninhalte. Je Domain höchstens LIMITS.history_max_per_domain Dateien. Alles lässt sich löschen."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .. import paths
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.limits import LIMITS
from ..core.redact import sanitize_obj
from .report import group_findings

VERSION = 1
MAX_BYTES = 2_000_000


def _flag() -> Path:
    return paths.config_dir() / "history.json"


def history_dir() -> Path:
    return paths.data_dir() / "history"


def enabled() -> bool:
    try:
        data = json.loads(_flag().read_text("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("enabled") is True


def set_enabled(value: bool) -> None:
    try:
        _flag().write_text(json.dumps({"enabled": bool(value)}), "utf-8")
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None


def _stem(host: str) -> str:
    return re.sub(r"[^a-z0-9.-]", "-", host.lower())[:60] or "site"


def record_of(result, now: datetime | None = None) -> dict:
    snap = result.snapshot
    when = now or datetime.now(UTC)
    record = {
        "version": VERSION, "saved": when.isoformat(timespec="seconds"), "host": snap.target.host,
        "level": snap.level, "profile": snap.profile, "status": snap.status,
        "score": result.scores["overall"], "categories": result.scores["categories"],
        "findings": [{"check_id": g["check_id"], "severity": g["severity"], "msg_de": g["msg_de"],
                      "msg_en": g["msg_en"], "count": g["count"]} for g in group_findings(result.findings)],
    }
    return sanitize_obj(record)


def runs(host: str) -> list[Path]:
    folder = history_dir()
    return sorted(folder.glob(f"{_stem(host)}_*.json")) if folder.is_dir() else []


def count(host: str | None = None) -> int:
    folder = history_dir()
    if not folder.is_dir():
        return 0
    return len(runs(host)) if host else len(list(folder.glob("*.json")))


def _valid(item) -> bool:
    return (isinstance(item, dict) and isinstance(item.get("check_id"), str)
            and isinstance(item.get("severity"), int) and 0 <= item["severity"] <= 4
            and isinstance(item.get("msg_de"), str) and isinstance(item.get("msg_en"), str)
            and isinstance(item.get("count"), int))


def load(path: Path) -> dict | None:
    """Liest und prüft eine Datei; beschädigte oder fremde Dateien werden ignoriert."""
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    if (not isinstance(data, dict) or data.get("version") != VERSION or not isinstance(data.get("findings"), list)
            or not isinstance(data.get("saved"), str) or not isinstance(data.get("score"), int)):
        return None
    return {**data, "findings": [item for item in data["findings"] if _valid(item)]}


def latest(host: str) -> dict | None:
    for path in reversed(runs(host)):
        record = load(path)
        if record is not None:
            return record
    return None


def save(record: dict, now: datetime | None = None) -> Path | None:
    """Speichert nur, wenn der Schalter an ist. Danach werden die ältesten Dateien der Domain entfernt."""
    if not enabled():
        return None
    stem = _stem(record["host"])
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%S%f")
    folder = history_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}_{stamp}.json"
        path.write_text(json.dumps(record, ensure_ascii=False), "utf-8")
        existing = runs(record["host"])
        for old in existing[: max(0, len(existing) - LIMITS.history_max_per_domain)]:
            old.unlink(missing_ok=True)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return path


def delete_all() -> int:
    folder = history_dir()
    removed = 0
    for path in list(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    try:
        folder.rmdir()
    except OSError:
        pass
    return removed


def _key(finding: dict) -> tuple:
    return (finding["check_id"], finding["severity"], finding["msg_de"])


def compare(old: dict, new: dict) -> dict:
    """Was ist neu, was behoben, was hat eine andere Anzahl. Verglichen wird je (Prüfung, Schwere, Text)."""
    before = {_key(f): f for f in old["findings"]}
    after = {_key(f): f for f in new["findings"]}

    def order(items):
        return sorted(items, key=lambda f: (-f["severity"], f["check_id"], f["msg_de"]))

    changed = [(before[k], after[k]) for k in after if k in before and before[k]["count"] != after[k]["count"]]
    return {
        "old_date": old["saved"], "new_date": new["saved"], "old_score": old["score"], "new_score": new["score"],
        "delta": new["score"] - old["score"],
        "level_changed": old.get("level") != new.get("level") or old.get("profile") != new.get("profile"),
        "added": order(after[k] for k in after if k not in before),
        "resolved": order(before[k] for k in before if k not in after),
        "changed": sorted(changed, key=lambda pair: (-pair[1]["severity"], pair[1]["check_id"])),
        "same": sum(1 for k in after if k in before and before[k]["count"] == after[k]["count"]),
    }
