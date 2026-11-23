"""Paket 23: Seitenleiste, Hilfe, Flaggen, Links, Befundliste, Splash-Hinweis, Ergebnisse ohne Hinweis im Lauf."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QApplication

from claudios.i18n.strings import t
from claudios.ui import pages as pages_module
from claudios.ui.activity import short_activity
from claudios.ui.finding_detail import _group_html, _linkify
from claudios.ui.helppage import HelpPage
from claudios.ui.linktext import LinkText, url_at_column, url_spans
from claudios.ui.main_window import MainWindow
from claudios.ui.pages import ScanPage
from claudios.ui.results_page import ResultsPage
from claudios.ui.splash import LOGO_HEIGHT, Splash
from claudios.ui.widgets import TitleBar, flag_icon

_APP = QApplication.instance() or QApplication([])


def test_short_activity_drops_addresses_and_dangling_separators():
    assert short_activity("Externe Links 3/200: https://example.com/x") == "Externe Links 3/200"
    assert short_activity("Link 4/9 (https://a.example/b)") == "Link 4/9"
    assert short_activity("Prüfung 5/100 BRW-AXE-001\nGeschätzt: 3 Min.") == "Prüfung 5/100 BRW-AXE-001"
    assert len(short_activity("x" * 200)) == 80


def test_url_spans_and_clicks():
    text = "go https://a.example/x, and https://b.example)"
    assert [text[s:e] for s, e in url_spans(text)] == ["https://a.example/x", "https://b.example"]
    assert url_at_column("go https://a.example/x, ok", 5) == "https://a.example/x"
    assert url_at_column("go https://a.example/x, ok", 0) is None
    assert url_at_column("see http://plain.example", 6) is None


def test_link_text_underlines_every_address():
    box = LinkText()
    box.setPlainText("a https://one.example b https://two.example")
    box.underline_links()
    assert len(box.extraSelections()) == 2


def test_linkify_escapes_and_keeps_trailing_dot_outside():
    html = _linkify("see https://a.example/x?a=1&b=2. ok <b>")
    assert '<a href="https://a.example/x?a=1&amp;b=2">' in html
    assert "</a>. ok &lt;b&gt;" in html


def test_affected_addresses_are_a_bullet_list_with_a_blank_line():
    group = {"severity": 2, "msg_de": "x", "msg_en": "x", "count": 1, "evidence": "https://dequeuniversity.com/rules",
             "example_urls": ["https://example.com/a", "https://example.com/b"]}
    html = _group_html(group, "en")
    assert html.count("<li>") == 2 and "<ul>" in html and "<p><br>" in html
    assert 'href="https://dequeuniversity.com/rules"' in html


def test_flags_are_drawn_and_differ():
    german, american = flag_icon("de"), flag_icon("en")
    assert not german.isNull() and not american.isNull()
    assert german.pixmap(24, 16).toImage() != american.pixmap(24, 16).toImage()


def test_titlebar_has_help_button_and_flag_buttons():
    bar = TitleBar(True)
    clicks = []
    bar.helpRequested.connect(lambda: clicks.append(1))
    bar.btn_help.click()
    assert clicks == [1]
    assert all(not btn.icon().isNull() for btn in bar._lang_buttons.values())
    assert TitleBar(False).btn_help.isHidden()


def test_splash_hint_comes_with_the_setup_and_the_logo_is_bigger():
    assert LOGO_HEIGHT == 251
    splash = Splash([])
    assert splash.hint.isHidden()
    splash.show_skip(True)
    assert not splash.hint.isHidden()
    splash._skip_timer.stop()
    splash.show_skip(False)
    assert splash.hint.isHidden()


def test_results_page_shows_no_empty_note_while_a_scan_runs(monkeypatch):
    monkeypatch.setattr("claudios.ui.results_page.latest_overall", lambda: None)
    page = ResultsPage()
    page.show_live("Prüfung 1/100", 5)
    page.retranslate()
    assert page.summary.text() == "" and page.live_bar.isHidden()
    page.hide_live()
    assert page.summary.text() == t("res.empty")


def test_help_page_has_both_documents_as_tabs():
    page = HelpPage()
    page.retranslate()
    assert page.tabs.count() == 2 and page.handbook.mode == "handbook" and page.tech.mode == "tech"


def test_main_window_has_help_in_the_title_bar_and_one_progress_bar():
    window = MainWindow({"language": "de", "allow_localhost": False})
    assert "nav.help" in window.nav_keys and "nav.handbook" not in window.nav_keys
    assert window.nav.item(window.nav_keys.index("nav.help")).isHidden()
    window.titlebar.btn_help.click()
    assert window.stack.currentWidget() is window.help
    assert window.handbook is window.help.handbook and window.tech is window.help.tech
    assert window.scan.bar.isHidden() and window.results.live_bar.isHidden()


def test_slow_checks_are_logged_with_their_duration(monkeypatch, caplog):
    page = ScanPage(lambda: {})
    ticks = iter([0.0, 10.0, 12.0])
    monkeypatch.setattr(pages_module.time, "monotonic", lambda: next(ticks))
    caplog.set_level(logging.INFO, logger="claudios")
    page._time_checks("check", "A-AAA-001")
    page._time_checks("check", "B-BBB-001")
    page._time_checks("end", "")
    assert "check A-AAA-001 took 10 s" in caplog.text and "B-BBB-001" not in caplog.text
