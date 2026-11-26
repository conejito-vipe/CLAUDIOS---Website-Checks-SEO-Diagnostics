"""Seite "Export": Dateien speichern, Abbruch im Dialog, Fehler mit Grund, Verlauf ein/aus/löschen, Hintergrund-Scan."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from test_exports import BAD, make_result

from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.ui import page_export, worker
from claudios.ui.page_export import ExportPage

_APP = QApplication.instance() or QApplication([])
Yes, No = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("HOME", str(tmp_path))
    state = {"infos": [], "errors": [], "answer": Yes, "path": ""}
    monkeypatch.setattr(page_export.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (state["path"], "")))
    monkeypatch.setattr(page_export.QMessageBox, "information", staticmethod(lambda *a: state["infos"].append(a[2])))
    monkeypatch.setattr(page_export.QMessageBox, "question", staticmethod(lambda *a: state["answer"]))
    monkeypatch.setattr(page_export, "show_error", lambda _w, data: state["errors"].append(data))
    monkeypatch.setattr(page_export, "error_info", lambda exc: {"error": str(exc)})
    return state


def page(result=None):
    p = ExportPage()
    p.retranslate()
    if result is not None:
        p.show_result(result)
    return p


def test_buttons_stay_disabled_until_there_is_a_result_and_exports_do_nothing_without_one(env):
    p = page()
    assert not any(b.isEnabled() for b in (p.csv_btn, p.xlsx_btn, p.pdf_btn, p.zip_btn))
    for kind in ("csv", "xlsx", "pdf"):
        p.export_file(kind)
    p.export_zip()
    assert env["infos"] == [] and env["errors"] == []
    p.show_result(make_result(BAD))
    assert all(b.isEnabled() for b in (p.csv_btn, p.xlsx_btn, p.pdf_btn, p.zip_btn))


@pytest.mark.parametrize("kind", ["csv", "xlsx", "pdf"])
def test_each_file_kind_is_written_to_the_chosen_path_and_reported(env, tmp_path, kind):
    p = page(make_result(BAD))
    env["path"] = str(tmp_path / f"bericht.{kind}")
    p.export_file(kind)
    target = Path(env["path"])
    assert target.is_file() and target.stat().st_size > 0 and len(env["infos"]) == 1 and env["path"] in env["infos"][0] and env["errors"] == []


def test_cancelling_the_file_dialog_writes_nothing(env, tmp_path):
    p = page(make_result(BAD))
    env["path"] = ""
    p.export_file("csv")
    p.export_zip()  # Ja bei der Vorschau, Abbruch im Dateidialog
    assert env["infos"] == [] and list(tmp_path.glob("*.csv")) == [] and list(tmp_path.glob("*.zip")) == []


def test_a_failing_export_shows_the_reason_and_never_claims_success(env, tmp_path, monkeypatch):
    p = page(make_result(BAD))
    env["path"] = str(tmp_path / "gone" / "a.csv")  # Ordner fehlt

    def boom(*_a):
        raise OSError("Platte voll")

    monkeypatch.setitem(page_export.KINDS, "csv", (boom, "CSV (*.csv)"))
    p.export_file("csv")
    assert env["infos"] == [] and "Platte voll" in env["errors"][0]["error"]


def test_the_zip_asks_first_and_writes_only_after_yes(env, tmp_path):
    p = page(make_result(BAD))
    env["path"] = str(tmp_path / "fokus.zip")
    env["answer"] = No
    p.export_zip()
    assert not Path(env["path"]).exists() and env["infos"] == []
    env["answer"] = Yes
    p.export_zip()
    assert Path(env["path"]).is_file() and len(env["infos"]) == 1 and env["path"] in env["infos"][0]


def test_zip_errors_in_preview_and_in_writing_are_shown(env, tmp_path, monkeypatch):
    p = page(make_result(BAD))
    monkeypatch.setattr(page_export, "focus_zip_preview", lambda *a: (_ for _ in ()).throw(ValueError("Vorschau kaputt")))
    p.export_zip()
    assert "Vorschau kaputt" in env["errors"][-1]["error"]
    monkeypatch.setattr(page_export, "focus_zip_preview", lambda *a: [("a.txt", 1)])
    monkeypatch.setattr(page_export, "build_focus_zip", lambda *a: (_ for _ in ()).throw(OSError("Schreibfehler")))
    env["path"] = str(tmp_path / "x.zip")
    p.export_zip()
    assert "Schreibfehler" in env["errors"][-1]["error"] and env["infos"] == []


def test_history_compare_save_switch_and_delete(env):
    p = page(make_result(BAD))
    assert p._diff is None and p.cmp.toPlainText()  # erster Scan: kein Vergleich
    p.show_result(make_result(BAD))  # zweiter Scan derselben Seite: Vergleich entsteht
    assert p._diff is not None and p.cmp.toPlainText()
    assert p.hist_delete.isEnabled()
    p.hist_box.setChecked(False)
    assert not page_export.history.enabled()
    p.hist_box.setChecked(True)
    assert page_export.history.enabled()
    env["answer"] = No
    p.delete_history()
    assert page_export.history.count() == 2 and env["infos"] == []
    env["answer"] = Yes
    p.delete_history()
    assert page_export.history.count() == 0 and not p.hist_delete.isEnabled()


def test_an_aborted_scan_is_not_stored_and_a_history_error_is_shown(env, monkeypatch):
    aborted = make_result(BAD)
    aborted.snapshot.status = "aborted"
    p = page(aborted)
    assert page_export.history.count() == 0 and p._aborted
    monkeypatch.setattr(page_export.history, "save", lambda _r: (_ for _ in ()).throw(OSError("kein Zugriff")))
    page(make_result(BAD))
    assert "kein Zugriff" in env["errors"][-1]["error"]


def test_a_failing_switch_of_the_history_is_shown(env, monkeypatch):
    p = page()
    monkeypatch.setattr(page_export.history, "set_enabled", lambda _c: (_ for _ in ()).throw(OSError("gesperrt")))
    p._toggle_history(False)
    assert "gesperrt" in env["errors"][-1]["error"]


def test_diff_text_truncates_long_lists_and_marks_a_changed_level():
    def entry(i):
        return {"severity": 2, "check_id": f"X-{i}", "msg_de": "m", "msg_en": "m"}

    diff = {"old_date": "2026-01-01T00:00", "old_score": 50, "new_score": 60, "delta": 10, "level_changed": True,
            "added": [entry(i) for i in range(page_export.MAX_LINES + 5)], "resolved": [],
            "changed": [({"count": 1}, dict(entry(1), count=3))], "same": 4}
    text = page_export.diff_text(diff, "de")
    assert text.count("- [") == page_export.MAX_LINES + 1 and "X-29" in text and "X-30" not in text and "+10" in text


def test_create_connects_the_page_to_the_scan_signal_when_there_is_one():
    seen = []
    signal = SimpleNamespace(connect=seen.append)
    created = page_export.create(SimpleNamespace(scan=SimpleNamespace(scan_finished=signal)))
    assert seen == [created.show_result] and isinstance(page_export.create(SimpleNamespace()), ExportPage)


# ---- ScanThread (Hintergrund-Scan) ----

def test_components_fall_back_to_nothing_installed_when_the_lock_is_broken(monkeypatch):
    monkeypatch.setattr(worker, "component_checker", lambda: (_ for _ in ()).throw(ValueError("kaputt")))
    assert worker._components()("zap") is False


def test_scan_thread_reports_result_error_and_cancel(monkeypatch):
    monkeypatch.setattr(worker, "scan_overrides", lambda *_a: {})
    monkeypatch.setattr(worker, "_components", lambda: (lambda _n: False))
    seen = {}

    async def fake_scan(**kw):
        kw["progress"]("fetch", 1, 2)
        seen["cancel_set"] = kw["cancel"].is_set()
        seen["stop"] = kw["stop_check"]()
        return "ergebnis"

    monkeypatch.setattr(worker, "run_scan", fake_scan)
    thread = worker.ScanThread({"raw_url": "example.com"})
    out, progress = [], []
    thread.done.connect(out.append)
    thread.progress.connect(lambda *a: progress.append(a))
    thread.cancel()  # schon vor dem Start abgebrochen: Ereignis und Prüfung sind sofort gesetzt
    thread.run()
    assert out == ["ergebnis"] and progress == [("fetch", 1, 2)] and seen == {"cancel_set": True, "stop": True}

    async def broken(**_kw):
        raise ClaudiosError(E.TARGET_PRIVATE)

    monkeypatch.setattr(worker, "run_scan", broken)
    thread = worker.ScanThread({"raw_url": "example.com"})
    failed = []
    thread.failed.connect(failed.append)
    thread.run()
    assert isinstance(failed[0], ClaudiosError)


def test_cancel_after_the_loop_has_ended_is_harmless():
    thread = worker.ScanThread({})
    loop = asyncio.new_event_loop()
    loop.close()
    thread._loop, thread._event = loop, asyncio.Event()
    thread.cancel()  # RuntimeError wird abgefangen
    assert thread._cancel_requested.is_set()
