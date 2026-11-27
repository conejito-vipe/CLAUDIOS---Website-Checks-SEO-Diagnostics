"""Screenshots des letzten Scans als ZIP speichern (nur auf Wunsch). Die Bilder werden nicht auf Geheimnisse geprüft:
sie zeigen, was ein Besucher sieht. Es zählen nur die erwarteten Dateinamen im Screenshot-Ordner des Programms."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.probe_shots import ALLOWED_FILES, shots_root


def files_of(result) -> list[Path]:
    data = result.snapshot.extra.get("shots")
    if not isinstance(data, dict) or data.get("skip"):
        return []
    folder = Path(str(data.get("dir", "")))
    try:
        if folder.resolve().parent != shots_root().resolve():
            return []
    except OSError:
        return []
    return [folder / name for name in data.get("files") or [] if name in ALLOWED_FILES and (folder / name).is_file()]


def folder_of(result) -> Path | None:
    """Ordner mit den Bildern dieses Scans (für die Anzeige „gespeichert in“), sonst None."""
    files = files_of(result)
    return files[0].parent if files else None


def add_to_archive(result, archive: zipfile.ZipFile) -> list[str]:
    """Legt die Bilder des Scans unter screenshots/ in ein ZIP (sie sind Teil des Berichts); gibt die Namen zurück."""
    names = []
    for path in files_of(result):
        archive.write(path, f"screenshots/{path.name}")
        names.append(f"screenshots/{path.name}")
    return names


def default_name(result) -> str:
    host = re.sub(r"[^a-z0-9.-]", "-", result.snapshot.target.host.lower())[:60]
    return f"CLAUDIOS-screenshots-{host}-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"


def build_zip(result, dest: Path | str) -> Path:
    files = files_of(result)
    if not files:
        raise ClaudiosError(E.EXPORT_FAILED, reason="no screenshots")
    dest = Path(dest)
    manifest = {"claudios_version": __version__, "created": datetime.now(UTC).isoformat(),
                "host": result.snapshot.target.host, "images_checked_for_secrets": False,
                "files": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                          for p in files}}
    try:
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as archive:
            for path in files:
                archive.write(path, path.name)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return dest
