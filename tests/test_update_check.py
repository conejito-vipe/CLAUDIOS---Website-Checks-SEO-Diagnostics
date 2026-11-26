"""Update-Hinweis beim Start: wann geprüft wird, wann angeboten wird, Fortschritt, Abbruch, Installer-Start."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from claudios import __version__
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.updater import ReleaseInfo
from claudios.ui import update_check
from claudios.ui.cardbox import SB

_APP = QApplication.instance() or QApplication([])


def info(version="99.0.0"):
    return ReleaseInfo(version, "https://example.invalid/r", "setup.exe", "https://example.invalid/setup.exe",
                       "https://example.invalid/setup.exe.sha256")


@pytest.fixture
def timers(monkeypatch):
    """Der Start nach 3 Sekunden wird aufgezeichnet statt ausgeführt."""
    calls = []
    monkeypatch.setattr(update_check.QTimer, "singleShot", staticmethod(lambda ms, fn: calls.append(ms)))
    return calls


def test_no_check_from_source_or_when_the_user_switched_it_off(timers):
    window = QWidget()
    assert update_check.start_update_check(window, {}, frozen=False) is None
    assert update_check.start_update_check(window, {"update_check": False}, frozen=True) is None
    assert timers == [] and not hasattr(window, "_update_thread")


def test_installed_program_checks_three_seconds_after_the_start(timers):
    window = QWidget()
    thread = update_check.start_update_check(window, {"update_check": True}, frozen=True)
    assert isinstance(thread, update_check.CheckThread) and window._update_thread is thread
    assert timers == [3000]
    assert update_check.start_update_check(QWidget(), {}, frozen=True) is not None  # Schlüssel fehlt = an


def test_an_offer_is_made_only_for_a_newer_version(timers, monkeypatch):
    offered = []
    monkeypatch.setattr(update_check, "offer", lambda window, found, settings: offered.append(found.version))
    thread = update_check.start_update_check(QWidget(), {}, frozen=True)
    thread.found.emit(info("99.0.0"))
    thread.found.emit(info(__version__))  # gleiche Version
    thread.found.emit(info("0.0.1"))  # ältere Version
    thread.found.emit(None)  # Prüfung ohne Ergebnis
    assert offered == ["99.0.0"]


def test_a_failing_check_never_disturbs_the_start(monkeypatch):
    def broken():
        raise OSError("kein Netz")

    monkeypatch.setattr(update_check.updater, "fetch_latest", broken)
    thread = update_check.CheckThread()
    seen = []
    thread.found.connect(seen.append)
    thread.run()
    assert seen == [None]


def test_progress_is_shown_in_percent_and_a_missing_total_means_zero():
    dialog = update_check.UpdateDialog(None, info())
    dialog._on_progress(50, 200)
    assert dialog.bar.value() == 25 and "25" in dialog.label.text()
    dialog._on_progress(10, 0)
    assert dialog.bar.value() == 0


def test_cancel_stops_the_download_but_closing_waits_for_the_thread():
    dialog = update_check.UpdateDialog(None, info())
    dialog.reject()  # Schließen = Abbruch; geschlossen wird erst, wenn der Thread sich meldet
    assert dialog.worker.cancel_event.is_set() and not dialog.cancel_btn.isEnabled()
    assert dialog.isVisible() is False and dialog.result() == QDialog.DialogCode.Rejected  # nicht von reject() geschlossen


def test_the_result_of_the_download_closes_the_dialog():
    dialog = update_check.UpdateDialog(None, info())
    dialog._on_result(Path("setup.exe"), None)
    assert dialog.path == Path("setup.exe") and dialog.error is None
    assert dialog.result() == QDialog.DialogCode.Accepted


class FakeDialog:
    path, error = None, None

    def __init__(self, _window, _info):
        pass

    def run(self):
        return type(self).path


@pytest.fixture
def install(monkeypatch):
    state = {"errors": [], "started": [], "quit": 0, "cards": [], "start_ok": True}
    FakeDialog.path, FakeDialog.error = None, None
    monkeypatch.setattr(update_check, "UpdateDialog", FakeDialog)
    monkeypatch.setattr(update_check, "error_info", lambda exc: {"error": str(exc)})
    monkeypatch.setattr(update_check, "show_error", lambda _window, data: state["errors"].append(data))
    monkeypatch.setattr(update_check.QProcess, "startDetached",
                        staticmethod(lambda path, args: state["started"].append((path, args)) or state["start_ok"]))
    monkeypatch.setattr(update_check.QApplication, "quit", staticmethod(lambda: state.__setitem__("quit", 1)))

    class Card:
        def __init__(self, _window, kind, _title, text):
            state["cards"].append((kind, text))

        def run(self):
            return None

    monkeypatch.setattr(update_check, "MessageCard", Card)
    return state


def test_a_cancelled_download_is_silent_but_other_errors_are_shown(install):
    FakeDialog.error = ClaudiosError(E.INSTALL_CANCELLED)
    update_check.install_update(None, info())
    assert install["errors"] == [] and install["started"] == []
    FakeDialog.error = RuntimeError("Prüfsumme falsch")
    update_check.install_update(None, info())
    assert len(install["errors"]) == 1 and "Prüfsumme falsch" in install["errors"][0]["error"]
    assert install["started"] == [] and install["quit"] == 0


def test_the_downloaded_installer_starts_silently_and_the_program_quits(install, tmp_path):
    FakeDialog.path = tmp_path / "setup.exe"
    update_check.install_update(None, info())
    assert install["started"] == [(str(tmp_path / "setup.exe"), update_check.SILENT_ARGS)] and install["quit"] == 1
    assert "/SILENT" in update_check.SILENT_ARGS and "/NORESTART" in update_check.SILENT_ARGS


def test_a_failed_installer_start_is_reported_and_the_program_keeps_running(install, tmp_path):
    FakeDialog.path = tmp_path / "setup.exe"
    install["start_ok"] = False
    update_check.install_update(None, info())
    assert install["quit"] == 0 and install["cards"] and install["cards"][0][0] == "warning"
    assert str(tmp_path / "setup.exe") in install["cards"][0][1]


@pytest.fixture
def offer_env(monkeypatch):
    state = {"answer": SB.Yes, "installed": 0, "saved": [], "extra": None}

    class Card:
        def __init__(self, _window, _kind, _title, _text, *, buttons, default, extra):
            state["extra"] = extra

        def run(self):
            return state["answer"]

        def reject(self):
            state["rejected"] = True

    monkeypatch.setattr(update_check, "MessageCard", Card)
    monkeypatch.setattr(update_check, "install_update", lambda _w, _i: state.__setitem__("installed", 1))
    monkeypatch.setattr(update_check, "save_settings", lambda settings: state["saved"].append(dict(settings)))
    return state


def test_the_installer_is_only_fetched_after_the_user_says_yes(offer_env):
    offer_env["answer"] = SB.No
    update_check.offer(None, info(), {})
    assert offer_env["installed"] == 0
    offer_env["answer"] = SB.Yes
    update_check.offer(None, info(), {})
    assert offer_env["installed"] == 1


def test_never_ask_again_switches_the_check_off_and_saves_it(offer_env):
    offer_env["answer"] = SB.No
    settings = {"language": "de"}
    update_check.offer(None, info(), settings)
    label, action = offer_env["extra"]
    assert label  # der Knopf ist beschriftet
    action()
    assert settings == {"language": "de", "update_check": False}
    assert offer_env["saved"] == [{"language": "de", "update_check": False}] and offer_env["installed"] == 0
