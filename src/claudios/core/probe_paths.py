"""Aktive Pfadprüfung (nur Stufe 2): feste Liste, nur GET über den Gatekeeper, keine Payloads, keine Weiterleitungen.
Ein Treffer zählt nur, wenn der Inhalt zur Datei passt (schützt vor Seiten, die auf alles mit 200 antworten).
Inhalte werden NIE gespeichert, nur Pfad, Art und Statuscode."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "paths"
MIN_LEVEL = 2
MAX_BYTES = 8192
NOT_HTML = {"vcs", "env", "htpasswd", "backup", "dsstore"}  # solche Dateien sind nie HTML
_LISTING = rb"(?i)<title>\s*Index of /"
_DUMP = rb"(?i)(CREATE TABLE|INSERT INTO|DROP TABLE|-- MySQL dump)"
_ZIP = rb"^PK\x03\x04"

# (Pfad, Art, Signatur im Inhalt)
PATHS = (
    (".git/HEAD", "vcs", rb"^ref: refs/"),
    (".git/config", "vcs", rb"\[core\]"),
    (".svn/wc.db", "vcs", rb"^SQLite format 3"),
    (".env", "env", rb"^[A-Z][A-Z0-9_]{2,}="),
    (".htpasswd", "htpasswd", rb"^[^:\s]+:(\$|\{SHA\}|[A-Za-z0-9./]{13})"),
    ("backup.zip", "backup", _ZIP), ("site.zip", "backup", _ZIP), ("www.zip", "backup", _ZIP),
    ("backup.sql", "backup", _DUMP), ("db.sql", "backup", _DUMP), ("dump.sql", "backup", _DUMP),
    ("database.sql", "backup", _DUMP),
    ("phpinfo.php", "phpinfo", rb"(?i)phpinfo\(\)|PHP Version"),
    ("info.php", "phpinfo", rb"(?i)phpinfo\(\)|PHP Version"),
    ("server-status", "status", rb"Apache Server Status"),
    ("web.config", "webconfig", rb"(?i)<configuration"),
    (".DS_Store", "dsstore", rb"^\x00\x00\x00\x01Bud1"),
    ("backup/", "listing", _LISTING), ("uploads/", "listing", _LISTING), ("files/", "listing", _LISTING),
    ("old/", "listing", _LISTING), ("tmp/", "listing", _LISTING), ("logs/", "listing", _LISTING),
    ("test/", "listing", _LISTING),
    ("phpmyadmin/", "admin", rb"phpMyAdmin"), ("adminer.php", "admin", rb"Adminer"),
    ("wp-login.php", "admin", rb"user_login"),
)


def _matches(kind: str, signature: bytes, status: int, ctype: str, body: bytes) -> bool:
    if status != 200:
        return False
    if kind in NOT_HTML and "html" in ctype:
        return False
    return re.search(signature, body[:MAX_BYTES], re.M) is not None


async def collect(gk, snap, resolver) -> dict:
    first = urlsplit(snap.pages[0].url)
    checked: list[dict] = []
    errors = 0
    for path, kind, signature in PATHS[: LIMITS.active_paths_max]:
        url = urlunsplit((first.scheme, first.netloc, "/" + path, "", ""))
        rec = {"path": path, "kind": kind, "status": None, "hit": False}
        try:
            resp = await gk.fetch(url, follow=False, max_bytes=MAX_BYTES)
        except ClaudiosError as exc:
            if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
                raise
            errors += 1
            checked.append(rec)
            continue
        rec["status"] = resp.status
        ctype = (resp.header("content-type") or "").lower()
        rec["hit"] = _matches(kind, signature, resp.status, ctype, resp.body)
        checked.append(rec)  # der Inhalt wird hier verworfen
    return {"total": len(checked), "errors": errors, "checked": checked}
