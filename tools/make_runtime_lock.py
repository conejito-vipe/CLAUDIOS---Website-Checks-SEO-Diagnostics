"""Erzeugt src/claudios/components/runtime-lock.json: feste Adressen und SHA256-Prüfsummen für die Python-Laufzeit
(embeddable, Windows) und die pip-Wheel-Datei. Läuft nur im Workflow 'Laufzeit-Sperrdatei erzeugen' (nicht im Programm).
Die Prüfsumme der pip-Datei wird gegen die Angabe von PyPI geprüft; die der Laufzeit steht als Annotation im Lauf und
lässt sich mit der Angabe auf python.org vergleichen. Bei jedem Fehler wird nichts geschrieben und der Lauf wird rot."""
from __future__ import annotations

import hashlib
import json
import re
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
PBS_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
PBS_ASSET = re.compile(r"^cpython-(3\.12\.\d+)\+\d+-aarch64-apple-darwin-install_only\.tar\.gz$")


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:600]}")


def fetch(url: str, limit: int = LIMIT) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
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


def choose_mac_runtime(release: dict) -> dict | None:
    """Das Archiv 'install_only' (Python 3.12, Apple-Chip) aus dem Release von python-build-standalone, sonst None."""
    for item in release.get("assets") or []:
        if isinstance(item, dict) and PBS_ASSET.match(str(item.get("name", ""))) \
                and str(item.get("browser_download_url", "")).startswith("https://"):
            return item
    return None


def sums_for(text: str, name: str) -> str | None:
    """Die SHA256 aus der Datei SHA256SUMS des Releases (Zeilen 'hash  name')."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return None


def mac_runtime() -> dict:
    release = json.loads(fetch(PBS_API))
    asset = choose_mac_runtime(release)
    if asset is None:
        raise ValueError("no macOS runtime found in the python-build-standalone release")
    sums = next((a for a in release["assets"] if a.get("name") == "SHA256SUMS"), None)
    if sums is None:
        raise ValueError("SHA256SUMS missing in the release")
    expected = sums_for(fetch(sums["browser_download_url"]).decode("utf-8", "replace"), asset["name"])
    data = fetch(asset["browser_download_url"], 400_000_000)
    digest = hashlib.sha256(data).hexdigest()
    if expected is None or digest != expected:
        raise ValueError("runtime checksum differs from SHA256SUMS of the release")
    return {"version": PBS_ASSET.match(asset["name"]).group(1), "url": asset["browser_download_url"],
            "sha256": digest, "size": len(data)}


def main_mac() -> int:
    """Nur den Mac-Eintrag ergänzen, die Windows-Einträge bleiben unverändert."""
    try:
        lock = json.loads(TARGET.read_text("utf-8"))
        lock["python_macos"] = mac_runtime()
    except Exception as exc:
        note("error", "Laufzeit-Sperrdatei (Mac)", f"{type(exc).__name__}: {exc}")
        return 1
    TARGET.write_text(json.dumps(lock, indent=2) + "\n", "utf-8")
    note("notice", "Mac-Laufzeit SHA256", f"{lock['python_macos']['version']}: {lock['python_macos']['sha256']}, von SHA256SUMS bestätigt")
    return 0


def main() -> int:
    if "--mac-only" in sys.argv:
        return main_mac()
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
    try:
        previous = json.loads(TARGET.read_text("utf-8")).get("python_macos")
    except (OSError, ValueError):
        previous = None
    lock = {
        "schema": 1,
        "python": {"version": PY_VERSION, "url": EMBED_URL, "sha256": embed_sha, "size": len(embed)},
        "pip": {"version": version, "url": wheel["url"], "sha256": wheel_sha, "size": len(wheel_data)},
    }
    if previous:
        lock["python_macos"] = previous
    TARGET.write_text(json.dumps(lock, indent=2) + "\n", "utf-8")
    note("notice", "Python-Laufzeit SHA256", f"{PY_VERSION}: {embed_sha} ({len(embed)} Bytes), bitte mit python.org vergleichen")
    note("notice", "pip-Wheel SHA256", f"{version}: {wheel_sha} ({len(wheel_data)} Bytes), von PyPI bestätigt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
