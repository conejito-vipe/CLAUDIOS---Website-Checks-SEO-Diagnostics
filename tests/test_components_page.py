"""Seite "Komponenten": Einrichtung im Hintergrund (Abbruch, Fehler mit Grund), Fortschritt, Entfernen mit Rückfragen."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from claudios.ui import components_page as cp

_APP = QApplication.instance() or QApplication([])
Yes, No = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


def comp(name):
    return SimpleNamespace(name=name, title=name.title())


@pytest.fixture
def env(monkeypatch):
    state = {"status": {}, "installed": [], "fail": {}, "errors": [], "infos": [], "answer": Yes, "uninstalled": None,
             "items": ["a"], "result": {}}
    comps = [comp("zap"), comp("node")]
    monkeypatch.setattr(cp, "load_lock", lambda: comps)
    monkeypatch.setattr(cp.manager, "status", lambda c: state["status"].get(c.name, "installed"))

    def install(c, progress=None, cancel=None):
        progress(c.name, "download", 1, 2)
        if c.name in state["fail"]:
            raise state["fail"][c.name]
        state["installed"].append(c.name)

    monkeypatch.setattr(cp.manager, "install", install)
    monkeypatch.setattr(cp.manager, "uninstall_items", lambda _l: state["items"])
    monkeypatch.setattr(cp.manager, "uninstall", lambda sel, _l: state["result"])
    monkeypatch.setattr(cp.info, "disk_size", lambda _c: 2048)
    monkeypatch.setattr(cp.info, "download_size_of", lambda c: (0, False) if c.name == "node" else (4096, True))
    monkeypatch.setattr(cp.info, "version_of", lambda _c: "1.0")
    monkeypatch.setattr(cp, "show_error", lambda _w, data: state["errors"].append(data))
    monkeypatch.setattr(cp, "error_info", lambda exc: {"error": str(exc)})
    monkeypatch.setattr(cp.QMessageBox, "information", staticmethod(lambda *a: state["infos"].append(a[2])))
    monkeypatch.setattr(cp.QMessageBox, "question", staticmethod(lambda *a: state["answer"]))
    state["comps"] = comps
    return state


def page():
    p = cp.ComponentsPage()
    p.retranslate()
    return p


def test_table_shows_one_row_per_component_with_sizes_and_a_dash_for_unknown_download(env):
    p = page()
    assert p.table.rowCount() == 2 and p.table.item(0, 0).text() == "Zap" and p.table.item(1, 2).text() == "–"
    assert p.total.text() and p.hint.text() == ""


def test_a_broken_lock_file_is_shown_instead_of_crashing(monkeypatch, env):
    monkeypatch.setattr(cp, "load_lock", lambda: (_ for _ in ()).throw(ValueError("kaputt")))
    p = page()
    assert p.table.rowCount() == 0 and "ValueError" in p.hint.text()


def test_install_thread_installs_in_order_collects_errors_and_stops_when_cancelled(env):
    env["fail"]["zap"] = RuntimeError("Download kaputt")
    thread = cp.InstallThread(env["comps"])
    out, seen = [], []
    thread.done.connect(out.append)
    thread.progress.connect(lambda *a: seen.append(a))
    thread.run()
    assert [(n_, type(e).__name__ if e else None) for n_, e in out[0]] == [("zap", "RuntimeError"), ("node", None)]
    assert env["installed"] == ["node"] and seen[0][:2] == ("zap", "download")
    cancelled = cp.InstallThread(env["comps"])
    out.clear()
    cancelled.done.connect(out.append)
    cancelled.cancel()
    cancelled.run()
    assert out == [[]]  # nichts mehr gestartet


def test_install_with_nothing_missing_says_so_and_starts_no_thread(env):
    p = page()
    p.install()
    assert p._thread is None and p.status.text()


def test_install_runs_in_the_background_locks_the_buttons_and_reports_failures(env, qtbot=None):
    env["status"] = {"zap": "missing"}
    env["fail"]["zap"] = RuntimeError("Prüfsumme falsch")
    p = page()
    p.install()
    assert p._thread is not None and not p.install_btn.isEnabled() and p.cancel_btn.isEnabled()
    p.install()  # zweiter Klick startet nichts Zweites
    p._thread.wait(10000)
    _APP.processEvents()
    assert p._thread is None and p.install_btn.isEnabled() and not p.cancel_btn.isEnabled()
    assert env["errors"] and "Prüfsumme falsch" in env["errors"][0]["error"] and p.bar.value() == 0


def test_progress_is_shown_in_percent_and_a_missing_total_means_zero(env):
    p = page()
    p._on_progress("zap", "download", 50, 200)
    assert p.bar.value() == 25 and "25" in p.status.text()
    p._on_progress("zap", "download", 5, 0)
    assert p.bar.value() == 0


def test_cancel_and_shutdown_stop_a_running_thread_and_do_nothing_otherwise(env):
    p = page()
    p.cancel()
    p.shutdown()  # ohne Thread: nichts passiert
    env["status"] = {"zap": "missing"}
    p.install()
    p.cancel()
    assert p._thread is None or p._thread._cancel.is_set()
    p.shutdown()
    _APP.processEvents()


def test_remove_needs_items_a_selection_and_a_confirmation(env, monkeypatch):
    p = page()
    env["items"] = []
    p.remove()
    assert env["infos"]  # Hinweis "nichts zu entfernen"
    env["items"] = ["a"]
    dialog = SimpleNamespace(exec=lambda: QDialog.DialogCode.Rejected, selected=lambda: ["a"])
    monkeypatch.setattr(cp, "UninstallDialog", lambda *a: dialog)
    env["infos"].clear()
    p.remove()
    assert env["infos"] == []
    dialog.exec = lambda: QDialog.DialogCode.Accepted
    dialog.selected = lambda: []
    p.remove()
    assert env["infos"] == []  # nichts ausgewählt
    dialog.selected = lambda: ["a", "b"]
    env["answer"] = No
    p.remove()
    assert env["infos"] == []  # nicht bestätigt
    env["answer"], env["result"] = Yes, {"a": None, "b": "gesperrt"}
    p.remove()
    assert len(env["infos"]) == 1 and "b" in env["infos"][0]


def test_remove_is_blocked_while_an_installation_runs(env):
    p = page()
    p._thread = object()
    p.remove()
    assert env["infos"] == []
