"""Absturz-Spur und Wächter: Datei, Wächter-Takt, Schließen und ein echter Hänger in einem eigenen Prozess."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

import claudios
from claudios.core import crashlog
from claudios.ui.heartbeat import Heartbeat

_APP = QApplication.instance() or QApplication([])


def test_install_writes_header_and_shutdown_closes(tmp_path):
    target = tmp_path / "logs" / "c.log"
    assert crashlog.install(target, crash_handler=False)
    assert crashlog.install(target, crash_handler=False)  # zweimal ist harmlos
    crashlog.arm(600)
    assert crashlog.armed()
    crashlog.disarm()
    assert not crashlog.armed()
    crashlog.shutdown()
    assert not crashlog.active()
    assert "=== CLAUDIOS" in target.read_text("utf-8")


def test_a_large_file_is_restarted(tmp_path):
    target = tmp_path / "c.log"
    target.write_text("x" * (crashlog.MAX_BYTES + 1), "utf-8")
    assert crashlog.install(target, crash_handler=False)
    crashlog.shutdown()
    assert target.stat().st_size < crashlog.MAX_BYTES


def test_install_failure_returns_false(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", "utf-8")
    assert crashlog.install(blocker / "sub" / "c.log", crash_handler=False) is False
    assert not crashlog.active()


def test_heartbeat_is_inactive_without_crash_log():
    crashlog.shutdown()
    beat = Heartbeat()
    assert not beat._timer.isActive()
    assert not crashlog.armed()


def test_heartbeat_arms_and_stops_when_installed(tmp_path):
    assert crashlog.install(tmp_path / "c.log", crash_handler=False)
    try:
        beat = Heartbeat()
        assert beat._timer.isActive() and crashlog.armed()
        beat.stop()
        assert not beat._timer.isActive() and not crashlog.armed()
    finally:
        crashlog.shutdown()


def test_watchdog_dumps_all_threads_when_not_rearmed(tmp_path):
    target = tmp_path / "hang.log"
    code = (
        "import time\n"
        "from pathlib import Path\n"
        "from claudios.core import crashlog\n"
        f"assert crashlog.install(Path({str(target)!r}))\n"
        "crashlog.arm(0.5)\n"
        "time.sleep(2)\n"
        "crashlog.shutdown()\n"
    )
    env = dict(os.environ, PYTHONPATH=str(Path(claudios.__file__).resolve().parent.parent))
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60, env=env)
    text = target.read_text("utf-8")
    assert "=== CLAUDIOS" in text and "most recent call first" in text
