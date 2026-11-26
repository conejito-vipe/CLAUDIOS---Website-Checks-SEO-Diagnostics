"""Lizenzschlüssel für die Pro-Seite: offline prüfbar, digital signiert (Ed25519), ohne Rückfrage ins Netz und ohne Nutzerdaten.

Dieselbe Schnittstelle wie die Verwaltung bei CONEJITO (Admin): Der Schlüssel heißt CL1.<Angaben base64url>.<Unterschrift base64url>.
Erzeugen kann ihn nur, wer den PRIVATEN Schlüssel hat (liegt nur beim Autor, nie im Repo). Im Programm steht nur der ÖFFENTLICHE Schlüssel.
Ist PUBLIC_KEYS leer (Auslieferungszustand), ist jeder Schlüssel ungültig und nichts wird gesperrt: die Pro-Seite bleibt inaktiv."""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

PREFIX = "CL1"
MAX_KEY_LEN = 4000
FILE = "lizenz.txt"
WARN_DAYS = 30

# Öffentliche Schlüssel der Verwaltung: kommen nur zur Laufzeit aus der lokalen Datei verwaltung.json (verwaltung.py), nie aus dem Quelltext.
PUBLIC_KEYS: dict[str, str] = {}

# Gesperrte Lizenz-IDs: fest im Programm, plus die aus der signierten Schaltdatei (schalt.py).
REVOKED: tuple[str, ...] = ()
REVOKED_EXTRA: tuple[str, ...] = ()
SCHALT_AKTIV = False

# Bereiche, die sich sperren lassen (Name -> Schlüssel des Anzeigetexts). Die Prüfung selbst ist nie sperrbar.
BEREICHE: tuple[str, ...] = ("export", "verlauf", "aktive_pruefungen")
GESPERRT_OHNE_LIZENZ: tuple[str, ...] = ()
IMMER_FREI = ("pruefung", "hilfe", "sprache", "lizenz", "beenden")

ARTEN = ("gewerblich", "gemeinnuetzig", "behoerde", "privat", "test")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}\Z")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")


def b64d(text: str) -> bytes:
    if not re.match(r"^[A-Za-z0-9_-]*\Z", text):
        raise ValueError("Zeichen")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def pubkey(kid: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = base64.b64decode(PUBLIC_KEYS[kid])
    if len(raw) != 32:
        raise ValueError("Länge")
    return Ed25519PublicKey.from_public_bytes(raw)


def _bad(reason: str) -> dict[str, Any]:
    return {"valid": False, "reason": reason}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def parse(key: Any, today: date | None = None) -> dict[str, Any]:
    """Prüft einen Schlüssel. Gibt immer ein Wörterbuch zurück, nie eine Ausnahme."""
    if not isinstance(key, str):
        return _bad("kein Text")
    key = "".join(key.split())  # Zeilenumbrüche aus E-Mails stören nicht
    if not key or len(key) > MAX_KEY_LEN:
        return _bad("leer oder zu lang")
    parts = key.split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return _bad("Format")
    try:
        body, sig = b64d(parts[1]), b64d(parts[2])
        data = json.loads(body.decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError, RecursionError):
        return _bad("Format")
    if not isinstance(data, dict):
        return _bad("Format")
    kid = data.get("kid")
    if not isinstance(kid, str) or kid not in PUBLIC_KEYS:
        return _bad("unbekannter Schlüssel")
    try:
        pubkey(kid).verify(sig, body)  # wirft bei jeder Abweichung, auch bei einem einzigen veränderten Byte
    except Exception:  # noqa: BLE001 – jede Abweichung heißt: ungültig
        return _bad("Unterschrift ungültig")
    lid, name, art, bis = data.get("id"), data.get("name"), data.get("art"), data.get("bis")
    areas = data.get("bereiche", "alle")
    if not (isinstance(lid, str) and _ID_RE.match(lid) and isinstance(name, str) and 0 < len(name) <= 120
            and art in ARTEN and isinstance(bis, str) and DATE_RE.match(bis)):
        return _bad("Angaben unvollständig")
    if areas != "alle" and not (isinstance(areas, list) and all(isinstance(b, str) and b in BEREICHE for b in areas)):
        return _bad("Angaben unvollständig")
    try:
        until = date.fromisoformat(bis)
    except ValueError:
        return _bad("Angaben unvollständig")
    days_left = (until - (today or date.today())).days
    out = {"valid": True, "reason": "", "id": lid, "name": " ".join(name.split()), "art": art, "until": bis,
           "days_left": days_left, "expired": days_left < 0, "areas": "alle" if areas == "alle" else list(areas)}
    if lid in REVOKED or lid in REVOKED_EXTRA:
        out.update(valid=False, reason="gesperrt")
    elif days_left < 0:
        out.update(valid=False, reason="abgelaufen")
    return out


def gesperrt_bereiche() -> tuple[str, ...]:
    """Ohne Lizenz gesperrt: fest im Code oder, wenn die Schaltdatei die Lizenzpflicht einschaltet, alle sperrbaren Bereiche."""
    return BEREICHE if SCHALT_AKTIV else GESPERRT_OHNE_LIZENZ


def path(base: Path) -> Path:
    return Path(base) / FILE


def load(base: Path) -> str:
    try:
        with open(path(base), encoding="utf-8") as fh:
            return fh.read(MAX_KEY_LEN + 10).strip()
    except (OSError, ValueError):  # auch ungültiges UTF-8 in der Datei: wie „keine Datei“
        return ""


def store(base: Path, key: str) -> dict[str, Any]:
    """Schlüssel prüfen und nur bei Erfolg (oder abgelaufen, damit der Hinweis bleibt) speichern."""
    res = parse(key)
    if res["valid"] or res.get("reason") == "abgelaufen":
        Path(base).mkdir(parents=True, exist_ok=True)
        atomic_write(path(base), "".join(str(key).split()))
    return res


def remove(base: Path) -> bool:
    try:
        path(base).unlink()
        return True
    except OSError:
        return False


def state(base: Path, today: date | None = None) -> dict[str, Any]:
    """Zustand für die Oberfläche: Schlüssel, ohne Lizenz gesperrte Bereiche, Hinweis auf nahen Ablauf."""
    key = load(base)
    res = parse(key, today) if key else {"valid": False, "reason": ""}
    valid = bool(res.get("valid"))
    covered = BEREICHE if valid and res.get("areas") == "alle" else tuple(res.get("areas") or ()) if valid else ()
    blocked = [b for b in gesperrt_bereiche() if b not in covered]
    return dict(res, has_key=bool(key), blocked=blocked, public_key_set=bool(PUBLIC_KEYS),
                warn_expiry=bool(valid and res["days_left"] <= WARN_DAYS))


def frei(base: Path, area: str) -> bool:
    """Darf dieser Bereich benutzt werden? Die Prüfung selbst: immer ja."""
    if area in IMMER_FREI or area not in gesperrt_bereiche():
        return True
    return area not in state(base)["blocked"]
