"""Windows-Härtung: Wiederholung bei PermissionError, Kopie als letzter Ausweg, Aufräumfehler im Cache."""
import os
import shutil
import tempfile

import pytest

from claudios.core import fsutil


def test_retry_succeeds_after_two_denials():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("denied")
        return "ok"

    assert fsutil.retry_permission(flaky, delays=(0.0, 0.0)) == "ok" and len(calls) == 3


def test_retry_gives_up_and_other_errors_pass_through():
    with pytest.raises(PermissionError):
        fsutil.retry_permission(lambda: (_ for _ in ()).throw(PermissionError("x")), delays=(0.0,))
    with pytest.raises(ValueError):
        fsutil.retry_permission(lambda: (_ for _ in ()).throw(ValueError("x")), delays=(0.0,))


def test_move_retries_the_rename(tmp_path, monkeypatch):
    src = tmp_path / "stage"
    src.mkdir()
    (src / "a.txt").write_text("x")
    dst = tmp_path / "node"
    real, state = os.rename, {"n": 0}

    def flaky(a, b):
        state["n"] += 1
        if state["n"] < 3:
            raise PermissionError("denied")
        return real(a, b)

    monkeypatch.setattr(fsutil, "DELAYS", (0.0, 0.0, 0.0))
    monkeypatch.setattr(os, "rename", flaky)
    assert fsutil.harden()
    try:
        shutil.move(str(src), str(dst))
    finally:
        fsutil.restore()
    assert (dst / "a.txt").read_text() == "x" and not src.exists() and state["n"] == 3


def test_move_copies_when_the_rename_stays_denied(tmp_path, monkeypatch):
    src = tmp_path / "stage"
    src.mkdir()
    (src / "a.txt").write_text("x")
    dst = tmp_path / "tools" / "node"
    dst.parent.mkdir()

    def deny(a, b):
        raise PermissionError("denied")

    monkeypatch.setattr(fsutil, "DELAYS", (0.0, 0.0))
    monkeypatch.setattr(os, "rename", deny)
    fsutil.harden()
    try:
        shutil.move(str(src), str(dst))
    finally:
        fsutil.restore()
    assert (dst / "a.txt").read_text() == "x" and not src.exists()


def test_harden_is_reversible_and_temp_dirs_work(tmp_path):
    original = (shutil.move, shutil.rmtree, tempfile.TemporaryDirectory)
    assert fsutil.harden() and not fsutil.harden()
    try:
        assert tempfile.TemporaryDirectory is not original[2]
        with tempfile.TemporaryDirectory(dir=tmp_path) as folder:
            assert os.path.isdir(folder)
    finally:
        fsutil.restore()
    assert (shutil.move, shutil.rmtree, tempfile.TemporaryDirectory) == original
