"""Mac-Werkzeuge: Varianten der Sperrdatei, Entpacken von tar.gz (Symlinks, Ausführrecht), npm-Pfad auf dem Mac."""
import io
import os
import tarfile
import zipfile

import pytest

from claudios.components import _shared, manager
from claudios.components.lock import load_lock, parse_lock
from claudios.core.errors import ClaudiosError

HEX = "a" * 64
BASE = {"name": "java", "title": "J", "kind": "archive", "version": "1", "url": "https://x.example/j.zip", "sha256": HEX,
        "size": 1, "license": "L", "source": "S", "exe": "**/bin/java.exe", "strip_top": True}
MAC = {"version": "2", "url": "https://x.example/j.tar.gz", "sha256": "b" * 64, "size": 2, "exe": "bin/java"}


def test_a_variant_replaces_address_checksum_and_program_only_on_the_mac():
    raw = {"schema": 1, "components": [{**BASE, "variants": {"macos": MAC}}]}
    win = parse_lock(raw, "windows")[0]
    mac = parse_lock(raw, "macos")[0]
    assert (win.sha256, win.exe) == (HEX, "**/bin/java.exe") and (mac.sha256, mac.exe) == ("b" * 64, "bin/java")
    assert mac.platforms == ("windows", "macos") and mac.url.endswith(".tar.gz")


@pytest.mark.parametrize("bad", [{**MAC, "sha256": ""}, {**MAC, "url": "http://x.example/j"}, {**MAC, "sha256": "zz"},
                                 {**MAC, "evil": "1"}])
def test_an_invalid_variant_is_refused(bad):
    with pytest.raises(ValueError):
        parse_lock({"schema": 1, "components": [{**BASE, "variants": {"macos": bad}}]}, "macos")


def test_unknown_systems_in_variants_are_refused():
    with pytest.raises(ValueError):
        parse_lock({"schema": 1, "components": [{**BASE, "variants": {"plan9": MAC}}]})


def test_the_shipped_lock_offers_the_tools_on_the_mac(monkeypatch):
    monkeypatch.setenv("CLAUDIOS_PLATFORM", "macos")
    names = {c.name for c in load_lock()}
    assert {"java", "node", "vnu", "css-validator", "zap", "npm-tools", "playwright"} <= names
    java = next(c for c in load_lock() if c.name == "java")
    assert java.exe.endswith("bin/java") and java.url.endswith(".tar.gz") and len(java.sha256) == 64


def _tar(path, items):
    with tarfile.open(path, "w:gz") as tf:
        for name, kind, data, extra in items:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tf.addfile(info)
            elif kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = data
                tf.addfile(info)
            elif kind == "hard":
                info.type = tarfile.LNKTYPE
                info.linkname = data
                tf.addfile(info)
            else:
                info.size = len(data)
                info.mode = extra
                tf.addfile(info, io.BytesIO(data))


def test_a_tar_gz_is_unpacked_with_links_and_the_run_permission(tmp_path):
    src = tmp_path / "a.tar.gz"
    _tar(src, [("top", "dir", None, 0), ("top/bin", "dir", None, 0), ("top/bin/node", "file", b"x", 0o755),
               ("top/lib/npm/cli.js", "file", b"y", 0o644), ("top/bin/npm", "sym", "../lib/npm/cli.js", 0)])
    out = tmp_path / "out"
    out.mkdir()
    manager.extract(src, out, True)
    assert os.access(out / "bin" / "node", os.X_OK) and not os.access(out / "lib" / "npm" / "cli.js", os.X_OK)
    assert (out / "bin" / "npm").is_symlink() and (out / "bin" / "npm").read_bytes() == b"y"


@pytest.mark.parametrize("items", [
    [("../evil", "file", b"x", 0o644)],
    [("/abs", "file", b"x", 0o644)],
    [("a/l", "sym", "../../outside", 0)],
    [("a/l", "sym", "/etc/passwd", 0)],
    [("a/h", "hard", "a/f", 0)],
])
def test_unsafe_tar_entries_are_refused(tmp_path, items):
    src = tmp_path / "a.tar.gz"
    _tar(src, [("a/f", "file", b"x", 0o644), *items])
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ClaudiosError):
        manager.extract(src, out, False)
    assert not (tmp_path / "evil").exists()


def test_a_broken_tar_gz_is_reported_as_corrupt(tmp_path):
    src = tmp_path / "a.tar.gz"
    src.write_bytes(b"\x1f\x8b" + b"nonsense")
    with pytest.raises(ClaudiosError):
        manager.extract(src, tmp_path, False)


def test_a_zip_keeps_the_run_permission(tmp_path):
    src = tmp_path / "a.zip"
    with zipfile.ZipFile(src, "w") as zf:
        for name, mode in (("zap.sh", 0o755), ("zap.jar", 0o644)):
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o100000 | mode) << 16
            zf.writestr(info, b"x")
    out = tmp_path / "out"
    out.mkdir()
    manager.extract(src, out, False)
    assert os.access(out / "zap.sh", os.X_OK) and not os.access(out / "zap.jar", os.X_OK)


def test_npm_is_found_in_the_mac_layout(tmp_path):
    cli = tmp_path / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("x")
    node = tmp_path / "bin" / "node"
    node.parent.mkdir()
    node.write_text("x")
    assert _shared.require_npm(node) == cli
