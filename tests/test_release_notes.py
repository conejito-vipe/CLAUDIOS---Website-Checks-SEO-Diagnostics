"""Release-Text im gleichen Aufbau wie bei CLAUDIA: Release Notes (Englisch, Deutsch aufklappbar) + Dateiliste + Prüfsumme."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

import claudios

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("release_body", ROOT / "tools" / "release_body.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_release_notes_belong_to_the_current_version_and_have_a_german_block(tool):
    text = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert tool.notes_version(text) == claudios.__version__
    assert "<details>" in text and "<summary>Deutsch</summary>" in text and text.count("# CLAUDIOS ") == 2


def test_the_body_lists_the_files_and_the_checksum_of_the_installer(tool, tmp_path):
    (tmp_path / f"CLAUDIOS-Setup-{claudios.__version__}.exe").write_bytes(b"setup")
    (tmp_path / "SHA256SUMS.txt").write_text("x")
    text = tool.body(tmp_path, (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"))
    assert "## Files" in text and "SHA256SUMS.txt" in text and "_Mac.zip" not in text
    assert text.rstrip().endswith("SHA-256: " + hashlib.sha256(b"setup").hexdigest())


def test_a_wrong_version_or_missing_installer_is_refused(tool, tmp_path):
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        tool.body(tmp_path, notes)
    (tmp_path / "CLAUDIOS-Setup-9.9.9.exe").write_bytes(b"x")
    with pytest.raises(ValueError):
        tool.body(tmp_path, notes, version="9.9.9")
