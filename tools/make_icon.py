"""Erzeugt assets/claudios.ico aus dem Logo (nur im Workflow 'Symbol erzeugen', nicht im Programm). Das Logo wird
quadratisch auf transparentem Grund zentriert; die Datei enthält 7 Größen von 16 bis 256 Pixel. Braucht Pillow (HPND-
Lizenz), das nur im Workflow installiert wird und nicht Teil des Programms ist."""
from __future__ import annotations

import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def pick_source(folder: Path) -> Path | None:
    for name in ("logo-icon.png", "logo-full.png"):
        if (folder / name).is_file():
            return folder / name
    return None


def build(source: Path, dest: Path) -> None:
    from PIL import Image

    image = Image.open(source).convert("RGBA")
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    canvas.save(dest, format="ICO", sizes=SIZES)


def main() -> int:
    source = pick_source(ASSETS)
    if source is None:
        print("::error title=Symbol::weder assets/logo-icon.png noch assets/logo-full.png gefunden")
        return 1
    dest = ASSETS / "claudios.ico"
    build(source, dest)
    print(f"::notice title=Symbol::{dest.name} aus {source.name} erzeugt ({dest.stat().st_size} Bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
