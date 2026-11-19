import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parent.parent / "tools" / "make_icon.py"
spec = importlib.util.spec_from_file_location("make_icon", PATH)
icon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icon)


def test_the_icon_source_prefers_the_icon_png_and_falls_back_to_the_logo(tmp_path):
    assert icon.pick_source(tmp_path) is None
    (tmp_path / "logo-full.png").write_bytes(b"x")
    assert icon.pick_source(tmp_path).name == "logo-full.png"
    (tmp_path / "logo-icon.png").write_bytes(b"x")
    assert icon.pick_source(tmp_path).name == "logo-icon.png"


def test_a_wide_logo_becomes_a_square_icon_with_several_sizes(tmp_path):
    image_module = pytest.importorskip("PIL.Image")
    source = tmp_path / "logo.png"
    image_module.new("RGBA", (300, 100), (238, 106, 18, 255)).save(source)
    dest = tmp_path / "claudios.ico"
    icon.build(source, dest)
    with image_module.open(dest) as result:
        assert dest.read_bytes()[:4] == b"\x00\x00\x01\x00" and result.size[0] == result.size[1]
