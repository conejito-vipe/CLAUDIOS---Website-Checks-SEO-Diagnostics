"""Symbol und Installer-Bilder: alle Symbolgrößen, Bildgrößen, Hintergrundfarbe, Zuschnitt auf den Inhalt."""
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
    assert {f.name for f in files} == {"app.ico", "wizard.bmp", "wizard-small.bmp"}
    sizes = set(Image.open(tmp_path / "art" / "app.ico").info["sizes"])
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
    big = Image.open(tmp_path / "art" / "wizard.bmp")
    assert big.size == module.WIZARD_SIZE and big.getpixel((0, 0)) == module.BG
    assert Image.open(tmp_path / "art" / "wizard-small.bmp").size == module.SMALL_SIZE


def test_build_without_logos_fails_clearly(tmp_path):
    module = _load()
    with pytest.raises(FileNotFoundError):
        module.build(tmp_path, tmp_path / "art")
