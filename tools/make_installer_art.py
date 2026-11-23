"""Erzeugt aus den Logos das Programmsymbol (ICO mit allen üblichen Größen von 16 bis 256 Pixel) und die Bilder des
Installers. Das Logo wird auf seinen Inhalt zugeschnitten und füllt das Symbol ohne Rand. Quelle für das Symbol und das kleine
Bild: assets/logo-mark.png (quadratisches Zeichen, falls vorhanden), sonst logo-icon.png, sonst logo-full.png. Großes
Seitenbild: Farbe des Hauptfensters (#E9EEF2). Kleines Bild oben rechts: Weiß, passend zur weißen Kopfzeile des
Installers (wirkt transparent). Die Ausgabe liegt in installer/art (wird nicht eingecheckt)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
BG = (0xE9, 0xEE, 0xF2)
WHITE = (255, 255, 255)
ICON_SIZES = (16, 24, 32, 48, 64, 96, 128, 256)
WIZARD_SIZE = (328, 628)   # doppelte Größe von 164x314; Inno Setup skaliert bei Bedarf herunter
SMALL_SIZE = (110, 110)    # doppelte Größe von 55x55
ICON_MARGIN = 0
SMALL_MARGIN = 14
MARK_NAMES = ("logo-mark.png", "logo-icon.png", "logo-full.png")


def crop_to_content(img: Image.Image) -> Image.Image:
    """Schneidet transparenten oder einfarbigen Rand ab."""
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        box = alpha.point(lambda v: 255 if v > 8 else 0).getbbox()
    else:
        background = Image.new("RGBA", rgba.size, rgba.getpixel((0, 0)))
        diff = ImageChops.difference(rgba, background).convert("L")
        box = diff.point(lambda v: 255 if v > 12 else 0).getbbox()
    return rgba.crop(box) if box else rgba


def on_canvas(logo: Image.Image, size: tuple[int, int], margin: int, background: tuple) -> Image.Image:
    canvas = Image.new("RGBA", size, background)
    inner_w, inner_h = size[0] - 2 * margin, size[1] - 2 * margin
    scale = min(inner_w / logo.width, inner_h / logo.height)
    scaled = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
                         Image.Resampling.LANCZOS)
    canvas.alpha_composite(scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2))
    return canvas


def _first(folder: Path, names: tuple[str, ...]) -> Path | None:
    return next((folder / name for name in names if (folder / name).is_file()), None)


def build(assets: Path, out: Path) -> list[Path]:
    mark_src = _first(assets, MARK_NAMES)
    wizard_src = _first(assets, ("logo-full.png", "logo-icon.png"))
    if mark_src is None or wizard_src is None:
        raise FileNotFoundError("assets/logo-full.png fehlt")
    out.mkdir(parents=True, exist_ok=True)
    mark = crop_to_content(Image.open(mark_src))
    wizard_logo = crop_to_content(Image.open(wizard_src))
    ratio = mark.width / mark.height
    if ratio > 1.3 or ratio < 0.77:
        print(f"::warning title=Symbol::Das Logo ist nicht quadratisch (Verhältnis {ratio:.2f}) und wirkt im Symbol klein. "
              "Lege ein quadratisches Zeichen als assets/logo-mark.png ab.")
    written = []
    ico = out / "app.ico"
    on_canvas(mark, (256, 256), ICON_MARGIN, (0, 0, 0, 0)).save(ico, format="ICO", sizes=[(s, s) for s in ICON_SIZES])
    written.append(ico)
    big = out / "wizard.bmp"
    on_canvas(wizard_logo, WIZARD_SIZE, 24, (*BG, 255)).convert("RGB").save(big, format="BMP")
    written.append(big)
    small = out / "wizard-small.bmp"
    on_canvas(mark, SMALL_SIZE, SMALL_MARGIN, (*WHITE, 255)).convert("RGB").save(small, format="BMP")
    written.append(small)
    return written


def main() -> int:
    try:
        files = build(ROOT / "assets", ROOT / "installer" / "art")
    except (OSError, ValueError) as exc:
        print(f"::warning title=Installer-Bilder::{exc}")
        return 1
    for path in files:
        print("geschrieben:", path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
