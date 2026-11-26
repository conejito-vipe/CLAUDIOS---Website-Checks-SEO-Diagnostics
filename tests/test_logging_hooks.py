"""Protokoll-Haken (Fehlerprotokoll, Absturz-Spur) und llms.txt-Probe: wirken, räumen auf, schreiben keine Werte und keine Geheimnisse."""
from __future__ import annotations

import logging
import sys
import threading
from types import SimpleNamespace

import pytest

from claudios.core import crashlog, errorlog, probe_ai
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.redact import RedactFilter


@pytest.fixture
def hooks(monkeypatch):
    """Stellt Fehlerklasse und Haken nach dem Test wieder her."""
    original_init = ClaudiosError.__init__
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    yield
    ClaudiosError.__init__ = original_init


def capture(logger_name="claudios.errors"):
    records = []

    class H(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = H(level=logging.DEBUG)
    handler.addFilter(RedactFilter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return records, lambda: logger.removeHandler(handler)


def test_every_claudios_error_is_logged_once_and_installing_twice_changes_nothing(hooks):
    records, stop = capture()
    try:
        errorlog.install()
        first = ClaudiosError.__init__
        errorlog.install()
        assert ClaudiosError.__init__ is first
        ClaudiosError(E.TARGET_PRIVATE)
        assert [r.getMessage() for r in records].count("error " + E.TARGET_PRIVATE.value + " {}") == 1
    finally:
        stop()


def test_secrets_in_error_details_never_reach_the_log_text(hooks):
    records, stop = capture()
    try:
        errorlog.install()
        ClaudiosError(E.TARGET_PRIVATE, detail="Authorization: Bearer abcdef0123456789secretvalue")
        assert records and all("abcdef0123456789secretvalue" not in r.getMessage() for r in records)
    finally:
        stop()


def test_uncaught_exceptions_in_the_main_and_in_threads_are_logged(hooks):
    records, stop = capture()
    try:
        errorlog.install()
        try:
            raise RuntimeError("main boom")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        thread = threading.Thread(target=lambda: (_ for _ in ()).throw(ValueError("thread boom")), name="worker-1")
        thread.start()
        thread.join()
        messages = [r.getMessage() for r in records]
        assert "uncaught exception" in messages and "uncaught exception in thread worker-1" in messages
        assert any(r.exc_info and r.exc_info[0] is RuntimeError for r in records)
        threading.excepthook(SimpleNamespace(thread=None, exc_type=KeyError, exc_value=KeyError("x"), exc_traceback=None))
        assert "uncaught exception in thread ?" in [r.getMessage() for r in records]
    finally:
        stop()


def test_the_start_line_names_version_and_python_but_nothing_personal():
    records, stop = capture("claudios")
    try:
        errorlog.log_startup()
        text = records[-1].getMessage()
        assert "CLAUDIOS" in text and "Python" in text and "frozen=" in text
    finally:
        stop()


@pytest.fixture
def crash(tmp_path):
    crashlog.shutdown()
    yield tmp_path / "logs" / crashlog.NAME
    crashlog.shutdown()


def test_the_crash_log_is_created_armed_and_closed_cleanly(crash):
    assert not crashlog.active() and crashlog.install(crash, crash_handler=False) and crashlog.active()
    assert crashlog.install(crash) is True  # zweites Mal ändert nichts
    assert "=== CLAUDIOS" in crash.read_text("utf-8") and not crashlog.armed()
    crashlog.arm(60)
    assert crashlog.armed()
    crashlog.disarm()
    assert not crashlog.armed()
    crashlog.shutdown()
    assert not crashlog.active()
    crashlog.arm()  # ohne Datei: nichts passiert
    assert not crashlog.armed()


def test_a_big_crash_log_is_started_fresh_and_a_small_one_is_appended(crash):
    crash.parent.mkdir(parents=True)
    crash.write_text("alt\n", "utf-8")
    crashlog.install(crash, crash_handler=False)
    crashlog.shutdown()
    assert crash.read_text("utf-8").startswith("alt\n")
    crash.write_text("x" * (crashlog.MAX_BYTES + 1), "utf-8")
    crashlog.install(crash, crash_handler=False)
    crashlog.shutdown()
    assert len(crash.read_text("utf-8")) < 200


def test_an_unusable_crash_log_path_never_stops_the_program(tmp_path):
    crashlog.shutdown()
    blocker = tmp_path / "datei"
    blocker.write_text("x", "utf-8")
    assert crashlog.install(blocker / "unter" / crashlog.NAME, crash_handler=False) is False and not crashlog.active()


def test_the_native_crash_trace_is_switched_on_and_off_with_the_file(crash):
    import faulthandler
    was = faulthandler.is_enabled()
    try:
        assert crashlog.install(crash, crash_handler=True) and faulthandler.is_enabled()
        crashlog.shutdown()
        assert not faulthandler.is_enabled()
    finally:
        if was:
            faulthandler.enable()


class GK:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    async def fetch(self, url, max_bytes=0):
        self.calls.append((url, max_bytes))
        if self.error:
            raise self.error
        return self.response


def llms_response(status=200, body=b"# Titel", ctype="Text/Plain", truncated=False):
    return SimpleNamespace(status=status, body=body, truncated=truncated, header=lambda _n: ctype)


async def test_llms_probe_asks_exactly_one_address_of_the_checked_site():
    snap = SimpleNamespace(pages=[SimpleNamespace(url="https://example.com/a/b?x=1")])
    gk = GK(llms_response())
    out = (await probe_ai.collect(gk, snap, None))["llms"]
    assert gk.calls == [("https://example.com/llms.txt", probe_ai.LIMITS.llms_body_max)]
    assert out["status"] == 200 and out["text"] == "# Titel" and out["content_type"] == "text/plain"


async def test_llms_probe_keeps_text_only_for_200_cuts_long_bodies_and_survives_bad_utf8():
    snap = SimpleNamespace(pages=[SimpleNamespace(url="https://example.com/")])
    out = (await probe_ai.collect(GK(llms_response(404, b"nicht da")), snap, None))["llms"]
    assert out["status"] == 404 and out["text"] == ""
    big = b"a" * (probe_ai.LIMITS.llms_body_max + 50)
    out = (await probe_ai.collect(GK(llms_response(body=big, truncated=True)), snap, None))["llms"]
    assert len(out["text"]) == probe_ai.LIMITS.llms_body_max and out["truncated"] is True
    out = (await probe_ai.collect(GK(llms_response(body=b"\xff\xfe ok")), snap, None))["llms"]
    assert "ok" in out["text"]


async def test_llms_probe_reports_errors_but_cancel_and_limit_go_up():
    snap = SimpleNamespace(pages=[SimpleNamespace(url="https://example.com/")])
    out = (await probe_ai.collect(GK(error=ClaudiosError(E.TARGET_PRIVATE)), snap, None))["llms"]
    assert out["error"] == E.TARGET_PRIVATE.value and out["status"] is None
    for code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
        with pytest.raises(ClaudiosError):
            await probe_ai.collect(GK(error=ClaudiosError(code)), snap, None)
