"""Schaltdatei der Verwaltung (SW1): schaltet die Lizenzpflicht ein/aus und liefert die Sperrliste, ohne neues Release.

Format SW1.<Angaben base64url>.<Unterschrift base64url>, signiert mit demselben privaten Schlüssel wie die Lizenzschlüssel, aber mit
eigenem Zweck (b"CONEJITO-SCHALT1\\n" + Angaben): eine Schaltdatei ist nie ein Lizenzschlüssel und umgekehrt.
Angaben: {"v":1,"kid":..,"aktiv":bool,"seit":"JJJJ-MM-TT","serial":N,"gesperrt":[Lizenz-IDs]}.
Die laufende Nummer darf nie sinken (Schutz gegen altes Zurückspielen). Bei Fehlern gilt der zuletzt geprüfte Stand weiter.
Der Abruf ist ein reines GET ohne Nutzerdaten, nur HTTPS, ohne Weiterleitung, mit Größengrenze, und nur auf Knopfdruck."""
from __future__ import annotations

import base64
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from . import lizenz

PREFIX = "SW1"
PURPOSE = b"CONEJITO-SCHALT1\n"
FILE = "schaltdatei.txt"
MAX_LEN = 60000
MAX_IDS = 5000
SCHALT_URL = ""  # Adresse der Schaltdatei der Verwaltung; leer = kein Abruf (nur Datei einlesen)
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}\Z")


def parse(text: Any, min_serial: int = 0) -> dict[str, Any] | None:
    """Prüft eine Schaltdatei. Gibt die Angaben zurück oder None (nie eine Ausnahme)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if not isinstance(text, str):
        return None
    text = "".join(text.split())
    if not text or len(text) > MAX_LEN:
        return None
    try:
        parts = text.split(".")
        if len(parts) != 3 or parts[0] != PREFIX:
            return None
        body, sig = lizenz.b64d(parts[1]), lizenz.b64d(parts[2])
        data = json.loads(body.decode("utf-8"))
        kid = data.get("kid") if isinstance(data, dict) else None
        if not isinstance(kid, str) or kid not in lizenz.PUBLIC_KEYS:
            return None
        Ed25519PublicKey.from_public_bytes(base64.b64decode(lizenz.PUBLIC_KEYS[kid])).verify(sig, PURPOSE + body)
        blocked, serial = data.get("gesperrt"), data.get("serial")
        if (data.get("v") != 1 or not isinstance(data.get("aktiv"), bool) or isinstance(serial, bool)
                or not isinstance(serial, int) or serial < max(1, min_serial)
                or not isinstance(data.get("seit"), str) or not lizenz.DATE_RE.match(data["seit"])
                or not isinstance(blocked, list) or len(blocked) > MAX_IDS
                or not all(isinstance(x, str) and _ID_RE.match(x) for x in blocked)):
            return None
        date.fromisoformat(data["seit"])
        return {"aktiv": data["aktiv"], "serial": serial, "seit": data["seit"], "gesperrt": tuple(blocked), "kid": kid}
    except Exception:  # noqa: BLE001 – jede Abweichung heißt: ungültig
        return None


def _path(base: Path) -> Path:
    return Path(base) / FILE


def load(base: Path) -> dict[str, Any] | None:
    try:
        with open(_path(base), encoding="utf-8") as fh:
            return parse(fh.read(MAX_LEN + 10))
    except OSError:
        return None


def apply(base: Path) -> dict[str, Any] | None:
    """Übernimmt den gespeicherten Stand in das Lizenzmodul (beim Start und nach jedem Einlesen aufrufen)."""
    data = load(base)
    lizenz.SCHALT_AKTIV = bool(data and data["aktiv"])
    lizenz.REVOKED_EXTRA = tuple(data["gesperrt"]) if data else ()
    return data


def accept(base: Path, text: Any) -> str:
    """Nimmt eine Schaltdatei an. '' bei Erfolg, sonst der Grund. Ältere Nummer oder falsche Unterschrift ändern nichts."""
    current = load(base)
    data = parse(text, current["serial"] if current else 0)
    if not data:
        return "ungültig oder älter als der bekannte Stand"
    Path(base).mkdir(parents=True, exist_ok=True)
    lizenz.atomic_write(_path(base), "".join(str(text).split()))
    apply(base)
    return ""


def _get(url: str) -> str:
    """Ein GET ohne Weiterleitung, höchstens MAX_LEN Byte, nur Status 200."""
    with httpx.Client(follow_redirects=False, timeout=10, headers={"User-Agent": "CLAUDIOS"}) as client:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError(response.status_code)
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > MAX_LEN:
                    break
    return data[: MAX_LEN + 1].decode("ascii", "strict")


def refresh(base: Path, url: str = "", fetch=None) -> dict[str, Any]:
    """Holt die Schaltdatei (GET, nur HTTPS, keine Weiterleitung). Nie eine Ausnahme; bei Fehlern bleibt der alte Stand."""
    url = url or SCHALT_URL
    if not url:
        return {"ok": False, "reason": "keine Adresse eingestellt"}
    if not url.lower().startswith("https://"):
        return {"ok": False, "reason": "nur https erlaubt"}
    try:
        text = (fetch or _get)(url)
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "nicht erreichbar"}
    why = accept(base, text)
    return {"ok": not why, "reason": why}
