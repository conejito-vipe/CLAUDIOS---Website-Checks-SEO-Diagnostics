#!/usr/bin/env python3
"""Stellt aus einem Ordner mit den fertigen Release-Dateien den GitHub-Release-Text zusammen (vom Workflow build-windows.yml
benutzt), im gleichen Aufbau wie bei CLAUDIA:

  python tools/release_body.py <Ordner mit den Dateien> [--notes RELEASE_NOTES.md] [--out release_body.md]

Der Text besteht aus
  1. den Release Notes (Englisch, Deutsch als aufklappbarer Block), unverändert aus RELEASE_NOTES.md,
  2. der Liste der Dateien dieses Releases (was jede Datei ist),
  3. der Zeile "SHA-256: <Prüfsumme des Windows-Installers>".
Prüfsummen weiterer Dateien stehen nur in SHA256SUMS.txt (Anhang), nicht im Text."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from claudios import __version__  # noqa: E402

SUMS = "SHA256SUMS.txt"
KINDS = [
    ("CLAUDIOS-Setup-{v}.exe", "Windows installer, single file, no Python needed (per user, no administrator rights)"),
    ("CLAUDIOS_v{v}_Mac.zip", "macOS (Apple silicon), CLAUDIOS.app, no Python needed; not notarized: first start via right click > Open"),
    (SUMS, "SHA-256 of every file of this release"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def notes_version(text: str) -> str:
    match = re.match(r"#\s*CLAUDIOS\s+(\d+\.\d+\.\d+)\b", text)
    return match.group(1) if match else ""


def body(folder: Path, notes_text: str, version: str = __version__) -> str:
    if notes_version(notes_text) != version:
        raise ValueError(f"RELEASE_NOTES.md gehört nicht zur Version {version}.")
    setup = folder / f"CLAUDIOS-Setup-{version}.exe"
    if not setup.is_file():
        raise ValueError(f"{setup.name} fehlt im Ordner.")
    present = {p.name for p in folder.iterdir()}
    rows = [f"- `{pattern.format(v=version)}`: {what}" for pattern, what in KINDS
            if pattern.format(v=version) in present]
    return notes_text.rstrip() + "\n\n## Files\n\n" + "\n".join(rows) + f"\n\nSHA-256: {sha256_file(setup)}\n"


def main(argv: list[str]) -> int:
    opts = {"--notes": str(ROOT / "RELEASE_NOTES.md"), "--out": "release_body.md"}
    args = []
    skip = False
    for i, arg in enumerate(argv[1:], 1):
        if skip:
            skip = False
        elif arg in opts and i + 1 < len(argv):
            opts[arg] = argv[i + 1]
            skip = True
        else:
            args.append(arg)
    if len(args) != 1:
        print(__doc__)
        return 2
    notes = Path(opts["--notes"]).read_text(encoding="utf-8")
    Path(opts["--out"]).write_text(body(Path(args[0]), notes), encoding="utf-8", newline="\n")
    print(f"Release-Text geschrieben: {opts['--out']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
