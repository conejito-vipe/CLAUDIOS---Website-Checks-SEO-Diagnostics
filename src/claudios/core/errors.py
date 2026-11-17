from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from importlib import resources

from .redact import redact_text


class ErrorCode(str, Enum):
    INPUT_EMPTY = "CLA-INP-001"
    INPUT_NOT_HTTPS = "CLA-INP-002"
    INPUT_CREDENTIALS = "CLA-INP-003"
    INPUT_INVALID = "CLA-INP-004"
    TARGET_PRIVATE = "CLA-TGT-001"
    TARGET_NO_DNS = "CLA-TGT-002"
    PERM_MISSING = "CLA-PRM-001"
    PERM_LEVEL2 = "CLA-PRM-002"
    LIMIT_COOLDOWN = "CLA-LIM-001"
    LIMIT_HOURLY = "CLA-LIM-002"
    LIMIT_DOMAIN_DAY = "CLA-LIM-003"
    LIMIT_BUSY = "CLA-LIM-004"
    LIMIT_BYTES = "CLA-LIM-005"
    LIMIT_DOMAIN_DAY_L2 = "CLA-LIM-006"
    TLS_CERT = "CLA-TLS-001"
    TLS_HANDSHAKE = "CLA-TLS-002"
    NET_TIMEOUT = "CLA-NET-001"
    NET_CONNECT = "CLA-NET-002"
    NET_REDIRECTS = "CLA-NET-003"
    NET_CROSS_SITE = "CLA-NET-004"
    NET_DOWNGRADE = "CLA-NET-005"
    SCAN_CANCELLED = "CLA-SCN-001"
    COMPONENT_MISSING = "CLA-CMP-001"
    TOOL_FAILED = "CLA-CMP-002"
    COMPONENT_NOT_PINNED = "CLA-CMP-003"
    DOWNLOAD_FAILED = "CLA-CMP-004"
    CHECKSUM_MISMATCH = "CLA-CMP-005"
    UNSAFE_ARCHIVE = "CLA-CMP-006"
    INSTALL_CANCELLED = "CLA-CMP-007"
    BROWSER_FAILED = "CLA-BRW-001"
    GOOGLE_AUTH = "CLA-GGL-001"
    GOOGLE_PROPERTY = "CLA-GGL-002"
    GOOGLE_IMPORT = "CLA-GGL-003"
    EXPORT_FAILED = "CLA-EXP-001"
    FS_ERROR = "CLA-FS-001"
    INTERNAL = "CLA-INT-001"


# Diese Fehler brechen nur die einzelne Seite/Prüfung ab, nicht den ganzen Scan.
NON_FATAL = {ErrorCode.NET_TIMEOUT, ErrorCode.NET_CONNECT, ErrorCode.NET_REDIRECTS,
             ErrorCode.TOOL_FAILED, ErrorCode.COMPONENT_MISSING, ErrorCode.BROWSER_FAILED}


class ClaudiosError(Exception):
    def __init__(self, code: ErrorCode, **ctx: object) -> None:
        self.code = code
        self.ctx = {k: redact_text(str(v))[:200] for k, v in ctx.items()}
        super().__init__(f"{code.value} {self.ctx}")

    @property
    def fatal(self) -> bool:
        return self.code not in NON_FATAL


class _Safe(dict):
    def __missing__(self, key: str) -> str:
        return "?"


@lru_cache(maxsize=1)
def catalog() -> dict:
    """Liest jede Datei errors*.json im Ordner i18n. Neue Meldungen = neue Datei."""
    data: dict = {}
    base = resources.files("claudios.i18n")
    for item in sorted(base.iterdir(), key=lambda p: p.name):
        if item.name.startswith("errors") and item.name.endswith(".json"):
            data.update(json.loads(item.read_text("utf-8")))
    return data


def describe(code: ErrorCode | str, lang: str = "en", **ctx: object) -> dict[str, str]:
    key = code.value if isinstance(code, ErrorCode) else str(code)
    if key not in catalog():
        key = ErrorCode.INTERNAL.value  # unbekannte Fehler: allgemeine Meldung
    title, cause, action = catalog()[key]["de" if lang == "de" else "en"]
    safe = _Safe({k: redact_text(str(v))[:200] for k, v in ctx.items()})
    return {"code": key, "title": title, "cause": cause.format_map(safe), "action": action.format_map(safe)}
