"""Codefenster für CSS und JavaScript: Quelltext aus der Probe 'assets', Inline-Code ohne falsche Zeilen."""
from __future__ import annotations

from types import SimpleNamespace as NS

from claudios.ui.code_source import source_for
from claudios.ui.finding_detail import code_excerpt, explain_html

CSS_URL = "https://example.com/a.css"
JS_URL = "https://example.com/app.js"
PAGE_URL = "https://example.com/"


def make_result(with_assets=True):
    extra = {}
    if with_assets:
        extra["assets"] = {
            "css": [
                {"url": CSS_URL, "status": 200, "error": None, "text": "a{}\nb{color:red}\nc{}\n", "truncated": False},
                {"url": "https://example.com/gone.css", "status": 404, "error": None, "text": "", "truncated": False},
            ],
            "js": [
                {"url": JS_URL, "status": 200, "error": None, "text": "var a = 1;\nvar b = eval(x);\n",
                 "truncated": False},
            ],
            "css_total": 2,
            "js_total": 1,
        }
    page = NS(url=PAGE_URL, html="<html>\n<body>\n<p>hi</p>\n</body>\n</html>")
    return NS(snapshot=NS(pages=[page], extra=extra))


def marked(excerpt):
    return [row for row in excerpt["lines"] if row[2]]


def test_css_asset_shows_the_stored_stylesheet():
    excerpt = code_excerpt(make_result(), [CSS_URL], "Line 2: Property colour", 3, check_id="CSS-VAL-001")
    assert excerpt is not None and excerpt["url"] == CSS_URL and excerpt["color"] == "red"
    assert marked(excerpt) == [(2, "b{color:red}", True)]


def test_js_asset_shows_the_stored_script():
    excerpt = code_excerpt(make_result(), [JS_URL], "Line 2: eval", 1, check_id="JSS-ESL-001")
    assert excerpt is not None and excerpt["url"] == JS_URL and excerpt["color"] == "yellow"
    assert marked(excerpt) == [(2, "var b = eval(x);", True)]


def test_inline_code_never_shows_the_page_lines():
    result = make_result()
    assert code_excerpt(result, [PAGE_URL], "Line 2: x", 2, check_id="JSS-ESL-001") is None
    assert code_excerpt(result, [PAGE_URL], "Line 2: x", 2, check_id="CSS-VAL-001") is None


def test_html_checks_still_show_the_page():
    excerpt = code_excerpt(make_result(), [PAGE_URL], "Line 2: x", 2, check_id="HTM-VAL-001")
    assert excerpt is not None and excerpt["url"] == PAGE_URL
    assert marked(excerpt) == [(2, "<body>", True)]
    assert code_excerpt(make_result(), [PAGE_URL], "Line 2: x", 2) is not None


def test_missing_or_failed_assets_give_no_source():
    assert source_for(make_result(), ["https://example.com/gone.css"], "CSS-VAL-001") is None
    assert source_for(make_result(False), [CSS_URL], "CSS-VAL-001") is None
    assert source_for(None, [CSS_URL]) is None


def test_explain_html_contains_the_stylesheet_lines():
    group = {"check_id": "CSS-VAL-001", "severity": 3, "msg_de": "CSS-Fehler", "msg_en": "CSS error", "count": 1,
             "evidence": "Line 2: boom", "example_urls": [CSS_URL]}
    html = explain_html("CSS-VAL-001", [group], ["CSS-Fehler"], "de", None, make_result())
    assert "b{color:red}" in html
