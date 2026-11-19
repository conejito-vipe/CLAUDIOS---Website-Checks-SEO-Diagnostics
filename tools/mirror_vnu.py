"""Spiegelt vnu.jar als feste Version in ein eigenes GitHub-Release und trägt Adresse, SHA256 und Größe in die
Sperrdatei ein (nur im Workflow 'vnu spiegeln', nicht im Programm). Grund: Das Release 'latest' des Projekts wird
laufend neu gebaut, eine Prüfsumme darauf hält nie. Geprüft wird die Datei gegen die SHA1-Liste des Betreibers und auf
ein gültiges JAR (Main-Class im Manifest). Die GPG-Signatur wird nicht geprüft. Bei jedem Fehler bleibt die Sperrdatei
unverändert und der Lauf wird rot."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "src" / "claudios" / "components" / "components.lock.json"
BASE = "https://github.com/validator/validator/releases/download/latest/"
LIMIT = 200_000_000


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:600]}")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Claudios-mirror"})
    with urllib.request.urlopen(request, timeout=300) as resp:
        data = resp.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Datei größer als 200 MB")
    return data


def listed_sha1(text: str) -> str:
    """Die SHA1 aus der Liste des Betreibers ('<hash>  vnu.jar'), leer bei unbrauchbarem Inhalt."""
    parts = text.strip().split()
    token = parts[0].lower() if parts else ""
    return token if re.fullmatch(r"[0-9a-f]{40}", token) else ""


def has_main_class(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return b"Main-Class" in archive.read("META-INF/MANIFEST.MF")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def parse_version(text: str) -> str:
    found = re.search(r"\d+\.\d+\.\d+(?:\.\d+)?", text)
    return found.group(0) if found else ""


def update_entry(raw: dict, *, version: str, url: str, sha256: str, size: int) -> bool:
    for entry in raw.get("components", []):
        if entry.get("name") == "vnu":
            entry.update(version=version, url=url, sha256=sha256, size=size, resolver={"type": "pinned"})
            return True
    return False


def run(cmd: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout, check=False)


def main() -> int:
    repo = os.environ.get("REPO", "")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        note("error", "vnu spiegeln", "Umgebungsvariable REPO fehlt oder ist ungültig")
        return 1
    try:
        jar = fetch(BASE + "vnu.jar")
        listed = listed_sha1(fetch(BASE + "vnu.jar.sha1").decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        note("error", "vnu spiegeln", f"Download fehlgeschlagen: {type(exc).__name__}")
        return 1
    if not listed or hashlib.sha1(jar, usedforsecurity=False).hexdigest() != listed:
        note("error", "vnu spiegeln", "Die Datei passt nicht zur SHA1-Liste des Betreibers")
        return 1
    sha256 = hashlib.sha256(jar).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "vnu.jar"
        path.write_bytes(jar)
        if not has_main_class(path):
            note("error", "vnu spiegeln", "Die Datei ist kein gültiges JAR (keine Main-Class)")
            return 1
        version = parse_version(run(["java", "-jar", str(path), "--version"], 120.0).stdout)
        tag = f"vnu-{version or 'build'}-{sha256[:8]}"
        if run(["gh", "release", "view", tag, "--repo", repo]).returncode == 0:
            note("notice", "vnu spiegeln", f"Release {tag} gibt es schon, es wird nur die Sperrdatei aktualisiert")
        else:
            notes = ("Gespiegelte Kopie von vnu.jar (W3C Nu Html Checker, MIT-Lizenz) aus dem Release 'latest' von "
                     "validator/validator, damit die Prüfsumme in der Sperrdatei dauerhaft stimmt. Geprüft gegen die "
                     "SHA1-Liste des Betreibers, die GPG-Signatur wurde nicht geprüft.")
            result = run(["gh", "release", "create", tag, str(path), "--repo", repo, "--title", f"vnu {version}",
                          "--notes", notes])
            if result.returncode != 0:
                note("error", "vnu spiegeln", f"Release nicht erstellt: {result.stderr[-300:]}")
                return 1
    url = f"https://github.com/{repo}/releases/download/{tag}/vnu.jar"
    raw = json.loads(LOCK.read_text("utf-8"))
    if not update_entry(raw, version=version or "latest", url=url, sha256=sha256, size=len(jar)):
        note("error", "vnu spiegeln", "Eintrag 'vnu' fehlt in der Sperrdatei")
        return 1
    LOCK.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", "utf-8")
    note("notice", "vnu gespiegelt", f"{tag}: {len(jar)} Bytes, sha256 {sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
