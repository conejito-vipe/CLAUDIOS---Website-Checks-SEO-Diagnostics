"""Vollansicht eines Befunds: Blättern, einheitliche Überschriften, weiße Links ohne Unterstreichung, orange beim Überfahren."""
import pytest

from claudios.checks import load_all
from claudios.core.registry import REGISTRY

load_all()

pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from claudios.ui import finding_detail  # noqa: E402
from claudios.ui.finding_detail import FindingDialog, explain_html  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _rows():
    return [["Fehler", cid, "1", "x"] for cid in list(REGISTRY)[:3]]


def test_the_dialog_pages_through_rows_and_shows_no_id():
    rows = _rows()
    dialog = FindingDialog(None, rows[0][1], [], rows[0], None, rows, 0)
    assert not dialog.prev_btn.isEnabled() and dialog.next_btn.isEnabled() and dialog.pos.text() == "1 / 3"
    dialog.next_btn.click()
    dialog.next_btn.click()
    assert dialog.index == 2 and not dialog.next_btn.isEnabled() and dialog.check_id == rows[2][1]
    assert rows[2][1] not in dialog.heading.text()
    dialog.step(5)  # über das Ende hinaus: bleibt stehen
    assert dialog.index == 2


def test_a_single_finding_has_no_paging_controls():
    rows = _rows()
    dialog = FindingDialog(None, rows[0][1], [], rows[0])
    assert dialog.prev_btn.isHidden() and dialog.next_btn.isHidden()


def test_all_headings_share_one_style_and_the_message_is_not_bold():
    group = {"check_id": list(REGISTRY)[0], "severity": 2, "msg_de": "Meldung", "msg_en": "Message", "count": 1, "evidence": "e",
             "example_urls": ["https://example.com/a"]}
    cid = list(REGISTRY)[0]
    html = explain_html(cid, [group], [cid, "Meldung"], "de")
    assert html.count(finding_detail.HEAD) >= 3 and "<b>" not in html and "font-size:12px" not in html


def test_links_are_white_without_underline_and_turn_orange_on_hover():
    group = {"check_id": list(REGISTRY)[0], "severity": 1, "msg_de": "m", "msg_en": "m", "count": 1, "evidence": "",
             "example_urls": ["https://example.com/a"]}
    cid = list(REGISTRY)[0]
    dialog = FindingDialog(None, cid, [group], [cid, "x"], None)
    dialog.resize(700, 600)
    dialog.show()
    _APP.processEvents()
    assert "text-decoration: none" in dialog.view.document().defaultStyleSheet()
    cursor = dialog.view.document().find("https://example.com/a")
    cursor.setPosition(cursor.selectionStart() + 5)
    rect = dialog.view.cursorRect(cursor)
    point = QPoint(rect.x() + 4, rect.y() + rect.height() // 2)
    dialog.hover.mark(point)
    selections = dialog.view.extraSelections()
    assert selections and selections[0].format.foreground().color().name().upper() == finding_detail.HOVER
    dialog.hover.mark(QPoint(2, 2))
    assert dialog.view.extraSelections() == []
