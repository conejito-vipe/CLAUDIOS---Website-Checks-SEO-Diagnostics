"""Fehlerprotokoll: jeder ClaudiosError erscheint im Log."""
import logging
import sys
import threading

from claudios.core import errorlog
from claudios.core.errors import ClaudiosError, ErrorCode


def test_error_creation_is_logged(caplog):
    original, hook, thread_hook = ClaudiosError.__init__, sys.excepthook, threading.excepthook
    try:
        errorlog.install()
        with caplog.at_level(logging.WARNING, logger="claudios.errors"):
            ClaudiosError(ErrorCode.TOOL_FAILED, reason="demo-reason")
        assert any("demo-reason" in record.getMessage() for record in caplog.records)
    finally:
        ClaudiosError.__init__ = original
        sys.excepthook, threading.excepthook = hook, thread_hook


def test_startup_line_is_written(caplog):
    with caplog.at_level(logging.INFO, logger="claudios"):
        errorlog.log_startup()
    assert any("started" in record.getMessage() for record in caplog.records)
