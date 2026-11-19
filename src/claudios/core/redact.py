"""Schwärzung beim Einlesen: Geheimnisse werden nie gespeichert. Zweite Schicht: Sanitizer vor dem Export.
Alle Muster müssen auch bei feindlichem Text in linearer Zeit laufen (Test: tests/test_hostile_input.py)."""
from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    # Erster Abschnitt begrenzt und ohne Zurücksetzen (possessiv): sonst braucht eine lange Folge ohne Punkt für
    # jeden Startpunkt quadratische Zeit.
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,300}+\.[A-Za-z0-9_-]{10,}+\.[A-Za-z0-9_-]{5,}+"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "stripe_key": re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{20,}"),
    "bearer": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
}
_KV = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization|client[_-]?secret)\b"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s\"'&,;<>]{3,})"
)
# Ein Treffer darf nur am Anfang eines Zeichenlaufs beginnen (Lookbehind): sonst wäre die Suche quadratisch.
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SENSITIVE_PARAM = re.compile(r"(pass|pwd|secret|token|key|auth|session|sess|sid|jwt|code|sig|credential|otp)", re.I)


def mask_secret(value: str) -> str:
    """Nur die ersten 4 Zeichen und die Länge: für Bericht-Belege."""
    return f"{value[:4]}…({len(value)})"


def redact_text(text: str) -> str:
    for name, pat in SECRET_PATTERNS.items():
        text = pat.sub(f"[REDACTED:{name}]", text)
    text = _KV.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return _EMAIL.sub("[email]", text)


def redact_url(url: str) -> str:
    """Entfernt Zugangsdaten, Fragment und sensible Query-Werte."""
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        netloc = f"[{host}]" if ":" in host else host
        if p.port:
            netloc += f":{p.port}"
        query = urlencode(
            [(k, "***" if _SENSITIVE_PARAM.search(k) else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
        )
        return redact_text(urlunsplit((p.scheme, netloc, p.path, query, "")))
    except ValueError:
        return "[invalid-url]"


def sanitize_obj(obj):
    """Rekursiv alle Strings eines Berichts schwärzen (Export-Sanitizer)."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: sanitize_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_obj(v) for v in obj]
    return obj


def find_leaks(text: str) -> list[str]:
    """Letzte Schranke vor dem Export: findet noch erkennbare Geheimnisse."""
    return [n for n, p in SECRET_PATTERNS.items() if p.search(text)]


class RedactFilter(logging.Filter):
    """Logging-Filter: keine Geheimnisse in Logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.getMessage()))
        record.args = ()
        return True
