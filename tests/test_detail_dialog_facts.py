"""Der Befund-Dialog nennt den Grund für ein fehlendes Codefenster mit technischen Angaben."""
from __future__ import annotations

from types import SimpleNamespace as NS

from claudios.i18n.strings import TEXTS, text
from claudios.ui.finding_detail import excerpt_facts, explain_html

KEYS = ("detail.facts_source", "detail.facts_range", "detail.facts_result", "detail.nogroups")


def make_result():
    return NS(snapshot=NS(pages=[NS(url="https://x/", html="a\nb")], extra={}))


def group(url="https://x/", evidence="Line 3: boom"):
    return {"check_id": "HTM-VAL-001", "severity": 3, "msg_de": "x", "msg_en": "x", "count": 1,
            "evidence": evidence, "example_urls": [url]}


def test_the_new_texts_exist_in_both_languages():
    for key in KEYS:
        assert key in TEXTS["de"] and key in TEXTS["en"]


def test_facts_for_an_address_without_stored_source():
    facts = excerpt_facts(make_result(), ["https://other/"], "Line 1: x", "HTM-VAL-001")
    assert facts["reason"] == "source" and facts["line"] == 1 and "other" in facts["url"]
    assert facts["pages"] == 1 and facts["samples"] == ["https://x/"] and facts["assets"] == 0


def test_facts_for_a_line_outside_the_text():
    facts = excerpt_facts(make_result(), ["https://x/"], "Line 9: x", "HTM-VAL-001")
    assert facts["reason"] == "range" and facts["lines"] == 2 and facts["line"] == 9


def test_no_facts_when_the_code_window_works_or_no_line_is_named():
    assert excerpt_facts(make_result(), ["https://x/"], "Line 2: x", "HTM-VAL-001") is None
    assert excerpt_facts(make_result(), ["https://x/"], "no line", "HTM-VAL-001") is None


def test_the_dialog_shows_the_reason_and_the_facts():
    html = explain_html("HTM-VAL-001", [group()], ["x"], "de", None, make_result())
    assert text("de", "detail.nocode_range") in html
    assert "hat nur 2 Zeilen" in html and "Zeile 3" in html
    html = explain_html("HTM-VAL-001", [group("https://other/", "Line 1: x")], ["x"], "en", None, make_result())
    assert "https://x/" in html and "1 pages with text" in html


def test_the_dialog_without_a_scan_result_still_names_the_reason():
    html = explain_html("HTM-VAL-001", [group()], ["x"], "de", None, None)
    assert text("de", "detail.nocode_result") in html and text("de", "detail.facts_result", line="3", url="https://x/") in html


def test_a_missing_findings_list_is_announced():
    html = explain_html("HTM-VAL-001", [], ["x"], "de", None, make_result())
    assert text("de", "detail.nogroups") in html
    assert text("de", "detail.nogroups") not in explain_html("HTM-VAL-001", [], ["x"], "de", None, None)
