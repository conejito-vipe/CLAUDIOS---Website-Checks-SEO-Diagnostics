from types import SimpleNamespace

import pytest

from claudios.core.findings import Finding, Severity as S
from claudios.i18n.strings import TEXTS, get_lang, set_lang
from claudios.ui import page_findings as pf

URL = "https://example.com/"


def result():
    findings = [
        Finding("SEC-HDR-002", S.WARNING, URL, "HSTS fehlt", "HSTS missing"),
        Finding("SEC-HDR-002", S.WARNING, URL + "a", "HSTS fehlt", "HSTS missing"),
        Finding("SEO-CAN-001", S.NOTE, URL, "Keine Canonical-URL", "No canonical URL", "x"),
        Finding("HTM-IMG-001", S.CRITICAL, URL, "Bild ohne alt", "Image without alt"),
    ]
    executed = {"SEC-HDR-002": "ran", "SEO-CAN-001": "ran", "SEC-TXT-001": "skipped:security_txt_unreachable"}
    return SimpleNamespace(findings=findings, executed=executed)


def test_findings_are_grouped_and_sorted_by_severity():
    rows = pf.collect(result())
    assert [r["check_id"] for r in rows] == ["HTM-IMG-001", "SEC-HDR-002", "SEO-CAN-001"]
    hsts = rows[1]
    assert hsts["count"] == 2 and hsts["urls"] == [URL, URL + "a"] and hsts["more"] == 0


def test_the_url_list_is_capped_and_the_rest_is_counted():
    many = [Finding("SEC-HDR-002", S.WARNING, f"{URL}p{i}", "x", "x") for i in range(pf.MAX_URLS + 5)]
    row = pf.collect(SimpleNamespace(findings=many, executed={}))[0]
    assert len(row["urls"]) == pf.MAX_URLS and row["more"] == 5


def test_filters_combine():
    rows = pf.collect(result())
    assert len(pf.visible(rows, 0, "", "", "de")) == 3
    assert [r["check_id"] for r in pf.visible(rows, 2, "", "", "de")] == ["HTM-IMG-001", "SEC-HDR-002"]
    assert [r["check_id"] for r in pf.visible(rows, 0, "SEO", "", "de")] == ["SEO-CAN-001"]
    assert [r["check_id"] for r in pf.visible(rows, 0, "", "hsts", "en")] == ["SEC-HDR-002"]
    assert [r["check_id"] for r in pf.visible(rows, 0, "", "example.com/a", "en")] == ["SEC-HDR-002"]
    assert pf.visible(rows, 0, "", "gibt-es-nicht", "de") == []


def test_checks_that_did_not_run_are_listed_with_their_reason():
    rows = pf.not_run(result())
    assert [r["check_id"] for r in rows] == ["SEC-TXT-001"]
    assert rows[0]["state"] == "skipped:security_txt_unreachable"
    assert len(pf.visible(rows, 4, "", "", "de")) == 1  # der Schwerefilter gilt hier nicht


def test_detail_text_contains_the_registry_texts():
    old = get_lang()
    try:
        set_lang("de")
        text = pf.detail_text(pf.collect(result())[1], "de")
        assert "SEC-HDR-002" not in text and text.startswith("HSTS") and "HSTS" in text and "Betroffene Seiten" in text
        assert "https://" in text and URL + "a" in text
        text = pf.detail_text(pf.not_run(result())[0], "de")
        assert "security_txt_unreachable" in text
    finally:
        set_lang(old)


def test_texts_exist_in_both_languages():
    keys = [k for k in TEXTS["de"] if k.startswith("fnd.")] + ["nav.findings"]
    assert len(keys) >= 15
    for key in keys:
        assert TEXTS["de"][key].strip() and TEXTS["en"][key].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_page_fills_after_a_scan_and_filters(qapp):
    from PySide6.QtCore import QObject, Signal

    class Scan(QObject):
        scan_finished = Signal(object)

    old = get_lang()
    try:
        set_lang("de")
        scan = Scan()
        page = pf.create(SimpleNamespace(scan=scan))
        page.retranslate()
        assert page.table.rowCount() == 0
        scan.scan_finished.emit(result())
        assert page.table.rowCount() == 3 and "HTM-IMG-001" not in page.detail.toPlainText() and "Bilder ohne Alternativtext" in page.detail.toPlainText()
        page.search.setText("hsts")
        assert page.table.rowCount() == 1 and "SEC-HDR-002" not in page.detail.toPlainText() and "HSTS" in page.detail.toPlainText()
        page.search.setText("")
        page.sev.setCurrentIndex(2)  # ab Warnung
        assert page.table.rowCount() == 2
        page.notrun.setChecked(True)
        assert page.table.rowCount() == 1 and "SEC-TXT-001" not in page.detail.toPlainText() and "security.txt" in page.detail.toPlainText()
    finally:
        set_lang(old)
