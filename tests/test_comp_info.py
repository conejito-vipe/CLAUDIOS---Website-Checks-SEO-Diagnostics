"""Anzeigedaten der Komponenten-Seite: Versionen aus den Sperrdateien, Download-Größen, belegter Platz."""
import json
import re

from claudios.components import info
from claudios.components.lock import Component, load_lock


def _comp(name: str, size: int = 0) -> Component:
    return Component(name=name, title=name, kind="file", version="", url="", sha256="", size=size, license="",
                     source="", depends=(), exe="x", filename="x", strip_top=False)


def test_versions_come_from_the_lock_files(tmp_path):
    comps = {c.name: c for c in load_lock()}
    npm = info.version_of(comps["npm-tools"], tmp_path)
    assert "ESLint" in npm and "Stylelint" in npm and "retire.js" in npm
    assert info.version_of(comps["playwright"], tmp_path).startswith("Playwright")
    assert re.match(r"\d+\.\d+", info.version_of(comps["sslyze"], tmp_path))
    assert info.version_of(comps["java"], tmp_path) == comps["java"].version


def test_installed_browser_versions_are_shown(tmp_path):
    folder = tmp_path / "playwright" / "node_modules" / "playwright-core"
    folder.mkdir(parents=True)
    (folder / "browsers.json").write_text(json.dumps({"browsers": [
        {"name": "chromium", "browserVersion": "9.9.9"}, {"name": "firefox", "browserVersion": "1.2"},
        {"name": "webkit", "revision": "77"}]}), "utf-8")
    assert "Chromium 9.9.9" in info.version_of(_comp("playwright"), tmp_path)
    assert info.version_of(_comp("pw-browsers"), tmp_path) == "Firefox 1.2, WebKit r77"


def test_download_sizes_are_exact_or_marked_as_estimates():
    assert info.download_size_of(_comp("java", 1234)) == (1234, False)
    size, approx = info.download_size_of(_comp("npm-tools"))
    assert size > 0 and approx
    assert info.download_size_of(_comp("unbekannt")) == (0, False)


def test_disk_size_splits_the_shared_browser_folder(tmp_path):
    browsers = tmp_path / "playwright" / "browsers"
    for name, size in (("chromium-1", 1000), ("firefox-2", 200), ("webkit-3", 300)):
        (browsers / name).mkdir(parents=True)
        (browsers / name / "f.bin").write_bytes(b"1" * size)
    (tmp_path / "playwright" / "x.bin").write_bytes(b"1" * 50)
    assert info.disk_size(_comp("pw-browsers"), tmp_path) == 500
    assert info.disk_size(_comp("playwright"), tmp_path) == 1050
    assert info.disk_size(_comp("node"), tmp_path) == 0
