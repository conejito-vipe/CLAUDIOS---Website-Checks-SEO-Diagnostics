"""Tausendertrenner, Verlauf nach Domain und Tag, Sprachsperre im Scan, Hilfe, Hover, Befund-Dialog."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace as NS

import pytest
from cssutil import rules
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from claudios.core.numtext import localize_numbers
from claudios.i18n.strings import get_lang, set_lang, t, text
from claudios.report import history
from claudios.report.history_tree import grouped
from claudios.ui.finding_detail import _group_html, _ordered, excerpt_problem, explain_html, meta_for, meta_text
from claudios.ui.helppage import HelpPage
from claudios.ui.highlight import CodeHighlighter
from claudios.ui.history_view import HistoryView
from claudios.ui.main_window import MainWindow
from claudios.ui.results_page import ResultsPage
from claudios.ui.theme import STYLE
from claudios.ui.theme_extra import EXTRA

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    old = get_lang()
    set_lang("de")
    yield tmp_path
    set_lang(old)


def record(host, saved):
    return {"version": 1, "saved": saved, "host": host, "level": 1, "profile": "standard", "status": "complete",
            "score": 80, "categories": {},
            "findings": [
                {"check_id": "SEC-HDR-001", "severity": 2, "msg_de": "Keine CSP", "msg_en": "No CSP", "count": 3},
                {"check_id": "CSS-STY-001", "severity": 1, "msg_de": "Regel (no-descending-specificity, 2019x)",
                 "msg_en": "Rule (no-descending-specificity, 2019x)", "count": 1}]}


def store_history():
    history.set_enabled(True)
    history.save(record("b.example", "2026-11-21T12:00:00+00:00"), now=datetime(2026, 11, 21, 12, 0, tzinfo=UTC))
    history.save(record("a.example", "2026-11-21T12:00:00+00:00"), now=datetime(2026, 11, 21, 12, 0, 1, tzinfo=UTC))
    history.save(record("a.example", "2026-11-22T12:00:00+00:00"), now=datetime(2026, 11, 22, 12, 0, tzinfo=UTC))


def test_numbers_get_separators_only_in_plain_text():
    assert localize_numbers("Regel (no-descending-specificity, 2019x)", "de") == "Regel (no-descending-specificity, 2.019x)"
    assert localize_numbers("rule (x, 2019x)", "en") == "rule (x, 2,019x)"
    assert localize_numbers("1445x und 12345 Zeichen", "de") == "1.445x und 12.345 Zeichen"
    for same in ("Jahr 2026", "TLS 1.2", "LCP nach 4.220 ms", "https://a.example/12345", "id=12345", "HTTP 404",
                 "CVE-2021-1234", "v1234", "Zeile 0123"):
        assert localize_numbers(same, "de") == same


def test_group_html_has_a_bold_message_first_and_localized_numbers():
    group = {"severity": 1, "msg_de": "CSS (rule, 2019x)", "msg_en": "CSS (rule, 2019x)", "count": 1, "evidence": "",
             "example_urls": []}
    html = _group_html(group, "de")
    assert html.startswith("<p><b>") and "2.019x" in html


def test_the_clicked_finding_comes_first_even_with_localized_numbers():
    groups = [{"check_id": "CSS-STY-001", "severity": 1, "msg_de": "A (2019x)", "msg_en": "A"},
              {"check_id": "CSS-STY-001", "severity": 1, "msg_de": "B (1445x)", "msg_en": "B"}]
    row = ["Hinweis", "CSS-STY-001", "1", "B (1.445x)"]
    assert _ordered("CSS-STY-001", groups, row, "de")[0]["msg_de"] == "B (1445x)"


def test_a_missing_code_window_gets_a_reason():
    assert excerpt_problem(None, ["https://x/"], "no line", "HTM-VAL-001") is None
    assert excerpt_problem(None, ["https://x/"], "Line 3: x", "HTM-VAL-001") == "result"
    result = NS(snapshot=NS(pages=[NS(url="https://x/", html="a\nb")], extra={}))
    assert excerpt_problem(result, ["https://other/"], "Line 1: x", "HTM-VAL-001") == "source"
    assert excerpt_problem(result, ["https://x/"], "Line 9: x", "HTM-VAL-001") == "range"
    assert excerpt_problem(result, ["https://x/"], "Line 2: x", "HTM-VAL-001") is None
    group = {"check_id": "HTM-VAL-001", "severity": 3, "msg_de": "x", "msg_en": "x", "count": 1,
             "evidence": "Line 3: boom", "example_urls": ["https://x/"]}
    assert text("de", "detail.nocode_result") in explain_html("HTM-VAL-001", [group], ["x"], "de", None, None)


def test_the_validator_texts_explain_the_rating():
    logic = meta_text(meta_for("HTM-VAL-001"), "logic", "de")
    assert "mindestens einen Fehler" in logic and "Hinweis" in logic
    assert "at least one error" in meta_text(meta_for("CSS-VAL-001"), "logic", "en")


def test_history_is_grouped_by_domain_and_day(env):
    store_history()
    tree = grouped()
    assert [host for host, _days in tree] == ["a.example", "b.example"]
    assert [day for day, _scans in tree[0][1]] == ["2026-11-22", "2026-11-21"]


def test_the_history_view_lists_domains_days_and_scans(env):
    store_history()
    view = HistoryView()
    view.retranslate()
    assert view.tree.topLevelItemCount() == 2
    host = view.tree.topLevelItem(0)
    assert host.text(0) == "a.example" and host.childCount() == 2
    day = host.child(0)
    assert day.text(0) == "2026-11-22" and day.childCount() == 1
    view.tree.setCurrentItem(day.child(0))
    detail = view.detail.toPlainText()
    assert "Content-Security-Policy" in detail and "SEC-HDR-001" not in detail and "2.019x" in detail


def test_the_history_view_says_so_when_it_is_empty(env):
    view = HistoryView()
    view.retranslate()
    assert view.tree.topLevelItemCount() == 0 and view.detail.toPlainText() == t("hv.empty")


def test_the_results_table_shows_numbers_with_separators(env):
    store_history()
    page = ResultsPage()
    page.retranslate()
    cells = [page.table.item(row, 3).text() for row in range(page.table.rowCount())]
    assert any("2.019x" in cell for cell in cells)


def test_the_language_is_locked_while_a_scan_runs(env):
    window = MainWindow({"language": "de", "allow_localhost": False})
    window.scan.running_changed.emit(True)
    assert all(not button.isEnabled() for button in window.titlebar._lang_buttons.values())
    window.set_language("en")
    assert get_lang() == "de"
    window.scan.running_changed.emit(False)
    assert all(button.isEnabled() for button in window.titlebar._lang_buttons.values())
    window.set_language("en")
    assert get_lang() == "en"


def test_the_results_page_stays_quiet_during_a_scan_and_speaks_after_it(env):
    window = MainWindow({"language": "de", "allow_localhost": False})
    window.scan.running_changed.emit(True)
    assert window.results.summary.text() == ""
    window.scan.running_changed.emit(False)
    assert window.results.summary.text() == t("res.empty")


def test_the_help_page_wraps_the_technical_text_and_marks_up_the_manual():
    page = HelpPage()
    page.retranslate()
    assert page.tech.view.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    assert page.handbook.view.document().findChildren(CodeHighlighter)


def test_flags_and_the_help_button_have_hover_and_active_styles():
    sheet = rules(STYLE + EXTRA)
    for state in ("hover", "checked", "disabled"):
        assert sheet[f"QPushButton#langbtn:{state}"], state  # jede Zustandsregel setzt mindestens eine Eigenschaft
    assert sheet["QPushButton#langbtn:checked"]["color"] != sheet["QPushButton#langbtn"]["color"]
    assert sheet["QLabel#pill"]["max-height"] == "15px"
