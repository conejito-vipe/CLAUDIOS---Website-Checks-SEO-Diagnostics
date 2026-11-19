"""Erzeugt src/claudios/components/runtime-lock.json: feste Adressen und SHA256-Prüfsummen für die Python-Laufzeit
(embeddable, Windows) und die pip-Wheel-Datei. Läuft nur im Workflow 'Laufzeit-Sperrdatei erzeugen' (nicht im Programm).
Die Prüfsumme der pip-Datei wird gegen die Angabe von PyPI geprüft; die der Laufzeit steht als Annotation im Lauf und
lässt sich mit der Angabe auf python.org vergleichen. Bei jedem Fehler wird nichts geschrieben und der Lauf wird rot."""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

PY_VERSION = "3.12.10"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
PIP_API = "https://pypi.org/pypi/pip/json"
TARGET = Path(__file__).resolve().parent.parent / "src" / "claudios" / "components" / "runtime-lock.json"
LIMIT = 80_000_000


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:600]}")


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as resp:
        data = resp.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("download too large")
    return data


def choose_wheel(data: dict) -> dict | None:
    """Die universelle Wheel-Datei (py3-none-any) aus der PyPI-Antwort, sonst None."""
    for item in data.get("urls") or []:
        if (isinstance(item, dict) and item.get("packagetype") == "bdist_wheel"
                and str(item.get("filename", "")).endswith("-py3-none-any.whl")
                and str(item.get("url", "")).startswith("https://")
                and isinstance((item.get("digests") or {}).get("sha256"), str)):
            return item
    return None


def main() -> int:
    try:
        embed = fetch(EMBED_URL)
        with zipfile.ZipFile(BytesIO(embed)) as archive:
            names = archive.namelist()
        if "python.exe" not in names or not any(name.endswith("._pth") for name in names):
            raise ValueError("python.exe or ._pth file missing in the archive")
        meta = json.loads(fetch(PIP_API))
        wheel = choose_wheel(meta)
        if wheel is None:
            raise ValueError("no pip wheel found at PyPI")
        wheel_data = fetch(wheel["url"])
        wheel_sha = hashlib.sha256(wheel_data).hexdigest()
        if wheel_sha != wheel["digests"]["sha256"].lower():
            raise ValueError("pip wheel checksum differs from the PyPI metadata")
        version = str((meta.get("info") or {}).get("version", ""))
    except Exception as exc:
        note("error", "Laufzeit-Sperrdatei", f"{type(exc).__name__}: {exc}")
        return 1
    embed_sha = hashlib.sha256(embed).hexdigest()
    lock = {
        "schema": 1,
        "python": {"version": PY_VERSION, "url": EMBED_URL, "sha256": embed_sha, "size": len(embed)},
        "pip": {"version": version, "url": wheel["url"], "sha256": wheel_sha, "size": len(wheel_data)},
    }
    TARGET.write_text(json.dumps(lock, indent=2) + "\n", "utf-8")
    note("notice", "Python-Laufzeit SHA256", f"{PY_VERSION}: {embed_sha} ({len(embed)} Bytes), bitte mit python.org vergleichen")
    note("notice", "pip-Wheel SHA256", f"{version}: {wheel_sha} ({len(wheel_data)} Bytes), von PyPI bestätigt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
