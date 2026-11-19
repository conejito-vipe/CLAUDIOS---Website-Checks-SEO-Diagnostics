import string
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from claudios.core import apikeys
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.gsc.credstore import MemoryStore
from claudios.i18n.brand import brand_all, branded
from claudios.i18n.strings import TEXTS, get_lang, set_lang
from claudios.ui import uninstall
from claudios.ui.boot_install import BootState, pending_components, run_schedule


def comp(name, *depends):
    return SimpleNamespace(name=name, depends=depends, title=name.upper())


def test_dependencies_are_installed_first_and_everything_finishes():
    order, lock = [], threading.Lock()

    def install(c):
        with lock:
            order.append(c.name)

    results = run_schedule([comp("b", "a"), comp("c", "a"), comp("a")], install, workers=3)
    assert order[0] == "a" and sorted(order) == ["a", "b", "c"]
    assert results == {"a": None, "b": None, "c": None}


def test_a_failed_component_fails_only_its_dependents():
    started = []

    def install(c):
        started.append(c.name)
        if c.name == "a":
            raise ClaudiosError(E.DOWNLOAD_FAILED, reason="x")

    results = run_schedule([comp("a"), comp("b", "a"), comp("c")], install, workers=2)
    assert results["a"].code == E.DOWNLOAD_FAILED and results["c"] is None
    assert results["b"].code == E.COMPONENT_MISSING and "b" not in started


def test_a_hanging_download_does_not_block_the_others():
    release, finished = threading.Event(), []

    def install(c):
        if c.name == "slow":
            release.wait(5)
            return
        finished.append(c.name)
        if len(finished) == 2:
            release.set()

    started = time.monotonic()
    results = run_schedule([comp("slow"), comp("x"), comp("y")], install, workers=2)
    assert release.is_set() and time.monotonic() - started < 4 and set(results) == {"slow", "x", "y"}


def test_cancel_before_the_start_installs_nothing():
    stop = threading.Event()
    stop.set()
    called = []
    assert run_schedule([comp("a")], lambda c: called.append(c), cancel=stop) == {} and called == []


def test_board_percent_and_text():
    board = BootState(2)
    board.update("a", 50, 100)
    assert board.percent() == 25 and "A 50 %" in board.active_text({"a": "A"})
    board.finish("a")
    board.update("a", 10, 100)  # späte Meldung nach dem Ende wird ignoriert
    assert board.finished == 1 and board.percent() == 50 and board.active_text({}) == "…"
    assert BootState(0).percent() == 100


def test_only_missing_non_optional_components_are_pending():
    comps = [SimpleNamespace(name="node"), SimpleNamespace(name="java"), SimpleNamespace(name="pw-browsers"),
             SimpleNamespace(name="zap")]
    state = {"node": "installed", "java": "missing", "pw-browsers": "missing", "zap": "outdated"}
    assert [c.name for c in pending_components(comps, lambda c: state[c.name])] == ["java", "zap"]
    assert pending_components(comps, lambda c: 1 / 0) == []


def test_the_name_is_written_in_capitals_without_touching_file_names():
    assert branded("Claudios läuft, siehe claudios.log") == "CLAUDIOS läuft, siehe claudios.log"
    table = {"de": {"a": "Claudios", "b": "x"}, "en": {"a": "About Claudios"}}
    assert brand_all(table) == 2 and table["en"]["a"] == "About CLAUDIOS" and table["de"]["b"] == "x"


def test_new_texts_exist_in_both_languages_with_the_same_placeholders():
    keys = [k for k in TEXTS["de"] if k.startswith(("boot.", "app.uninstall", "res.summary_aborted"))]
    assert len(keys) >= 9
    for key in keys:
        names = [{f for _lit, f, _spec, _conv in string.Formatter().parse(TEXTS[lang][key]) if f}
                 for lang in ("de", "en")]
        assert TEXTS["de"][key].strip() and TEXTS["en"][key].strip() and names[0] == names[1], key
    assert set(TEXTS["de"]) == set(TEXTS["en"])


def test_the_uninstaller_is_only_used_in_the_built_program(tmp_path):
    exe = tmp_path / "Claudios.exe"
    assert uninstall.uninstaller_path(exe, frozen=False) is None
    assert uninstall.uninstaller_path(exe, frozen=True) is None
    (tmp_path / "unins000.exe").write_bytes(b"x")
    assert uninstall.uninstaller_path(exe, frozen=True) == tmp_path / "unins000.exe"


def test_removal_keeps_the_scan_log_and_deletes_keys_and_history(monkeypatch):
    removed, history = [], []
    items = [SimpleNamespace(key="tool:java"), SimpleNamespace(key="cache"), SimpleNamespace(key="logs")]
    monkeypatch.setattr(uninstall.manager, "uninstall_items", lambda *a, **k: items)
    monkeypatch.setattr(uninstall.manager, "uninstall", lambda keys, *a, **k: removed.extend(keys) or {k: None for k in keys})
    monkeypatch.setattr(uninstall.history, "delete_all", lambda: history.append(1))
    monkeypatch.setitem(apikeys._STATE, "store", MemoryStore())
    apikeys.set_key("pagespeed", "p" * 30)
    assert uninstall.perform_removal() == []
    assert removed == ["tool:java", "cache", "logs"] and history == [1]
    assert not apikeys.has_key("pagespeed") and not any("audit" in key for key in removed)


def test_a_failing_part_is_reported_and_the_rest_continues(monkeypatch):
    monkeypatch.setattr(uninstall.manager, "uninstall_items", lambda *a, **k: [SimpleNamespace(key="cache")])
    monkeypatch.setattr(uninstall.manager, "uninstall", lambda keys, *a, **k: {"cache": "PermissionError"})
    monkeypatch.setattr(uninstall.history, "delete_all", lambda: 1 / 0)
    monkeypatch.setitem(apikeys._STATE, "store", MemoryStore())
    assert uninstall.perform_removal() == ["cache", "history"]


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_window_edges_are_found_and_a_fixed_size_window_has_none(qapp):
    from PySide6.QtCore import QPoint, Qt

    from claudios.ui.widgets import MARGIN, CardWindow

    window = CardWindow(with_lang=False)
    window.resize(400, 300)
    assert window._edges_at(QPoint(2, 150)) == Qt.Edge.LeftEdge
    assert window._edges_at(QPoint(398, 150)) == Qt.Edge.RightEdge
    assert window._edges_at(QPoint(398, 2)) == Qt.Edge.TopEdge | Qt.Edge.RightEdge
    assert not window._edges_at(QPoint(200, 150)) and MARGIN > 0
    fixed = CardWindow(with_lang=False)
    fixed.setFixedSize(400, 300)
    assert not fixed._edges_at(QPoint(2, 150))


def test_an_aborted_scan_shows_no_overall_score(qapp):
    from claudios.ui.results_page import ResultsPage

    snap = SimpleNamespace(status="aborted", target=SimpleNamespace(url="https://example.com/"), pages=[])
    result = SimpleNamespace(snapshot=snap, findings=[], executed={}, scores={"overall": 0, "categories": {}},
                             requests=0, bytes_total=0)
    old = get_lang()
    try:
        set_lang("de")
        page = ResultsPage()
        page.retranslate()
        page.show_result(result)
        assert "keine Gesamtwertung" in page.summary.text() and "/100" not in page.summary.text()
    finally:
        set_lang(old)


async def test_an_aborted_scan_gets_no_score(tmp_path):
    from claudios.core.audit_log import AuditLog
    from claudios.core.engine import run_scan

    class Broken:
        async def addresses(self, host):
            raise ClaudiosError(E.TARGET_NO_DNS, host=host)

    result = await run_scan("example.com", level=1, confirmed=True, audit=AuditLog(tmp_path / "audit.jsonl"),
                            lock_path=tmp_path / "scan.lock", resolver=Broken())
    assert result.snapshot.status == "aborted" and result.scores == {"overall": 0, "categories": {}}


def test_the_installer_script_uses_the_full_title_and_a_placeholder_for_the_author():
    root = Path(__file__).resolve().parent.parent
    text = (root / "installer" / "claudios.iss").read_text("utf-8")
    assert "CLAUDIOS - Website-Checks-SEO-Diagnostics" in text and "[AUTHOR_NAME]" in text
    assert "AppPublisher=GitHub - " in text and "OutputBaseFilename=Claudios-Setup-" in text
