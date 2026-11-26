"""Dunkles Design (Entwurf B): Kontraste, Stilvorlagen, Icon-Leiste, Startscreen und Hilfe mit Inhaltsverzeichnis."""
from __future__ import annotations

import re

import pytest
from PySide6.QtWidgets import QApplication

from claudios.core.registry import REGISTRY
from claudios.i18n.strings import TEXTS, set_lang, t
from claudios.ui import finding_detail, highlight, theme
from claudios.ui.helppage import HelpPage
from claudios.ui.main_window import MainWindow
from claudios.ui.navicons import PATHS, nav_icon
from claudios.ui.theme import STYLE
from claudios.ui.theme_extra import EXTRA

_APP = QApplication.instance() or QApplication([])


def _luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("fg,bg,minimum", [
    (theme.INK, theme.BG, 7), (theme.INK, theme.SURFACE, 7), (theme.INK, theme.BG_DEEP, 7),
    (theme.MUTED, theme.BG, 4.5), (theme.MUTED, theme.SURFACE, 4.5), (theme.MUTED, theme.BG_DEEP, 4.5),
    (theme.ON_ORANGE, theme.ORANGE, 4.5), (theme.ON_ORANGE, theme.ORANGE_HI, 4.5),
    (theme.ORANGE_HI, theme.BG, 4.5), (theme.ORANGE_HI, theme.ORANGE_SOFT, 4.5), (theme.ORANGE, theme.BG, 4.5),
])
def test_text_colors_are_readable_on_their_backgrounds(fg, bg, minimum):
    assert contrast(fg, bg) >= minimum


def test_syntax_link_and_excerpt_colors_are_readable_on_the_dark_code_areas():
    for name, color in highlight.COLORS.items():
        if name != "rule":  # die Trennlinie ist Dekoration, kein Text
            assert contrast(color, theme.BG_DEEP) >= 4.5, name
    assert contrast("#8EC0FF", theme.BG_DEEP) >= 4.5  # Links (linktext.py)
    for name, background in finding_detail.COLORS.items():
        assert contrast(theme.INK, background) >= 4.5, name  # Text auf farbig hinterlegter Zeile des Codefensters


def test_style_sheets_have_no_unreplaced_placeholders():
    assert not re.findall(r"%[A-Z_0-9]+%", STYLE)
    assert not re.findall(r"%[A-Z_0-9]+%", EXTRA)


def test_every_navigation_key_has_a_drawn_icon_and_the_fallback_is_distinct():
    window = MainWindow({"language": "de", "allow_localhost": False})
    for index, key in enumerate(window.nav_keys):
        item = window.nav.item(index)
        assert item.text() == t(key) and item.toolTip() == t(key)  # Text bleibt für Tooltip und Screenreader
        assert not item.icon().isNull()
        if key != "nav.help":  # „Hilfe“ ist verborgen und hat trotzdem ein Symbol
            assert key in PATHS, f"kein Symbol für {key}"
    image = nav_icon("nav.scan").pixmap(22).toImage()
    assert any(image.pixelColor(x, y).alpha() > 0 for x in range(image.width()) for y in range(image.height()))


def test_start_screen_has_title_form_card_and_info_card_in_both_languages():
    window = MainWindow({"language": "de", "allow_localhost": False})
    page = window.scan
    assert page.title.text() == t("scan.title") and page.subtitle.text() == t("scan.subtitle")
    assert all(label.text() for label in page.info_heads + page.info_bodies)
    for key in [k for k in TEXTS["de"] if k.startswith(("scan.info", "scan.title", "scan.subtitle", "doc.title"))]:
        assert TEXTS["en"].get(key), f"englischer Text fehlt: {key}"
    set_lang("en")
    try:
        page.retranslate()
        assert page.title.text() == TEXTS["en"]["scan.title"]
    finally:
        set_lang("de")
        page.retranslate()


def test_help_toc_lists_every_check_and_a_click_scrolls_to_it():
    page = HelpPage()
    page.resize(900, 500)
    page.show()
    page.retranslate()
    toc, view = page.handbook.toc, page.handbook.view
    assert toc.count() == len(REGISTRY) > 20
    last = toc.count() - 1
    toc.setCurrentRow(last)
    _APP.processEvents()
    check_id = toc.item(last).text().split()[0]
    assert check_id in view.textCursor().block().text()  # der Cursor steht auf der Überschrift des Eintrags
    assert view.verticalScrollBar().value() > 0


def test_shared_search_filters_both_tabs_marks_hits_and_clears():
    page = HelpPage()
    page.retranslate()
    full = page.handbook.toc.count()
    page.search.setText("hsts")
    _APP.processEvents()
    assert 0 < page.handbook.toc.count() < full
    assert page.handbook.toc.item(0).text().split()[0].startswith("SEC-")
    marked = [s.cursor.selectedText().lower() for s in page.handbook.view.extraSelections()
              if s.format.background().color().name() == "#6b4310"]
    assert marked and set(marked) == {"hsts"}
    page.tabs.setCurrentIndex(1)  # der andere Reiter wird beim Wechsel mit derselben Suche neu gezeichnet
    assert page.tech.search.text() == "hsts" and 0 < page.tech.toc.count() < full
    page.search.setText("zzz-keine-treffer")
    assert page.tech.toc.count() == 0 and t("doc.none") in page.tech.view.toPlainText()
    page.search.setText("")
    assert page.tech.toc.count() == full


def test_help_title_names_the_version_and_the_search_box_is_in_the_header():
    page = HelpPage()
    page.retranslate()
    from claudios import __version__
    assert __version__ in page.title.text()
    assert page.search.placeholderText() == t("doc.search")
    assert page.handbook.search.isHidden() and page.tech.search.isHidden()


def test_score_colors_are_readable_and_graded():
    from claudios.ui.scorecards import BAD, GOOD, WARN, score_color
    assert [score_color(v) for v in (100, 80, 79, 50, 49, 0)] == [GOOD, GOOD, WARN, WARN, BAD, BAD]
    for color in (GOOD, WARN, BAD):
        assert contrast(color, theme.SURFACE) >= 4.5 and contrast(color, theme.BG) >= 4.5


def test_results_head_shows_ring_and_one_card_per_category_but_nothing_for_an_aborted_scan():
    from types import SimpleNamespace

    from claudios.ui.pages import ResultsPage

    def result(status, overall, cats):
        snap = SimpleNamespace(status=status, pages=[], target=SimpleNamespace(url="https://example.com/"))
        return SimpleNamespace(snapshot=snap, scores={"overall": overall, "categories": cats}, requests=1,
                               bytes_total=10, executed={}, findings=[])

    page = ResultsPage()
    page.retranslate()
    assert page.head.isHidden()  # ohne Ergebnis keine Wertung
    page.show_result(result("complete", 72, {"seo": 90, "security": 54}))
    assert not page.head.isHidden() and page.ring.value == 72
    assert [(c.name, c.score) for c in page.categories.cards] == [("seo", 90), ("security", 54)]
    page.show_result(result("aborted", 0, {}))
    assert page.head.isHidden() and page.ring.value is None and not page.categories.cards
    image = page.ring.grab().toImage()  # der Ring lässt sich zeichnen, auch ohne Wert
    assert image.width() == page.ring.width()


def test_severity_colors_are_readable_and_applied_to_the_table():
    from types import SimpleNamespace

    from claudios.ui.pages import ResultsPage
    from claudios.ui.scorecards import SEVERITY
    for color in SEVERITY.values():
        assert contrast(color, theme.BG_DEEP) >= 4.5
    finding = {"severity": 4, "check_id": "SEC-HDR-001", "count": 1, "msg_de": "x", "msg_en": "x", "evidence": "",
               "example_urls": []}
    import claudios.ui.pages as pages
    original = pages.group_findings
    pages.group_findings = lambda _f: [finding]
    try:
        page = ResultsPage()
        page.retranslate()
        snap = SimpleNamespace(status="complete", pages=[], target=SimpleNamespace(url="https://example.com/"))
        page.show_result(SimpleNamespace(snapshot=snap, scores={"overall": 50, "categories": {}}, requests=1,
                                         bytes_total=1, executed={}, findings=[]))
    finally:
        pages.group_findings = original
    assert page.table.item(0, 0).foreground().color().name().lower() == SEVERITY[4].lower()


def test_navigation_shows_the_logo_on_top_and_a_label_under_every_icon():
    from claudios.ui.navicons import RAIL_W, RailDelegate
    window = MainWindow({"language": "de", "allow_localhost": False})
    assert window.logo.pixmap() is not None or window.logo.text() == "CLAUDIOS"
    assert window.nav.itemDelegate().sizeHint(None, None).width() == RAIL_W - 8
    assert isinstance(window.nav.itemDelegate(), RailDelegate)
    window.show()
    _APP.processEvents()
    shot = window.nav.grab().toImage()
    # unter dem Symbol des ersten Eintrags liegen gezeichnete Textpixel (Beschriftung)
    row = window.nav.visualItemRect(window.nav.item(0))
    band = [shot.pixelColor(x, y) for x in range(row.x(), row.right()) for y in range(row.y() + 34, row.y() + 48)]
    assert len({c.name() for c in band}) > 2
