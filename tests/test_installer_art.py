"""Symbol und Installer-Bilder: alle Symbolgrößen, Bildgrößen, Hintergrundfarben, Zuschnitt auf den Inhalt, kein Rand."""
import importlib.util
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("make_installer_art", ROOT / "tools" / "make_installer_art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _logo(path: Path) -> None:
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (200, 100), (238, 106, 18, 255)), (100, 50))
    img.save(path)


def test_crop_removes_the_empty_border():
    module = _load()
    logo = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    logo.paste(Image.new("RGBA", (200, 100), (238, 106, 18, 255)), (100, 50))
    assert module.crop_to_content(logo).size == (200, 100)


def test_build_writes_icon_and_wizard_images(tmp_path):
    module = _load()
    assets = tmp_path / "assets"
    assets.mkdir()
    _logo(assets / "logo-full.png")
    _logo(assets / "logo-icon.png")
    files = module.build(assets, tmp_path / "art")
    assert {f.name for f in files} == {"app.ico", "app.icns", "wizard.bmp", "wizard-small.bmp"}
    assert (tmp_path / "art" / "app.icns").read_bytes()[:4] == b"icns"  # Mac-Symbol
    sizes = set(Image.open(tmp_path / "art" / "app.ico").info["sizes"])
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
    big = Image.open(tmp_path / "art" / "wizard.bmp")
    assert big.size == module.WIZARD_SIZE and big.getpixel((0, 0)) == module.BG
    small = Image.open(tmp_path / "art" / "wizard-small.bmp")
    assert small.size == module.SMALL_SIZE and small.getpixel((0, 0)) == module.WHITE


def test_the_logo_fills_the_icon_without_a_margin():
    module = _load()
    logo = Image.new("RGBA", (50, 50), (238, 106, 18, 255))
    canvas = module.on_canvas(logo, (256, 256), module.ICON_MARGIN, (0, 0, 0, 0))
    assert canvas.getpixel((0, 0))[3] == 255 and canvas.getpixel((255, 255))[3] == 255


def test_a_square_mark_is_preferred_for_the_icon(tmp_path):
    module = _load()
    assets = tmp_path / "assets"
    assets.mkdir()
    _logo(assets / "logo-full.png")
    Image.new("RGBA", (64, 64), (10, 20, 30, 255)).save(assets / "logo-mark.png")
    module.build(assets, tmp_path / "art")
    icon = Image.open(tmp_path / "art" / "app.ico")
    icon.size = (256, 256)
    assert icon.convert("RGBA").getpixel((128, 128))[:3] == (10, 20, 30)


def test_build_without_logos_fails_clearly(tmp_path):
    module = _load()
    with pytest.raises(FileNotFoundError):
        module.build(tmp_path, tmp_path / "art")
