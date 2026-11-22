"""Codefenster der Befund-Erklärung: Zeilen um den Treffer, Farbe nach Schwere, Maskierung, Links nur mit https."""
from types import SimpleNamespace

from claudios.ui import finding_detail as fd

HTML = "\n".join(f"<p>line {i}</p>" for i in range(1, 21)) + "\n"


def _result():
    page = SimpleNamespace(url="https://a.test/", html=HTML)
    return SimpleNamespace(snapshot=SimpleNamespace(pages=[page]))


def test_the_excerpt_marks_the_line_and_picks_the_color_by_severity():
    red = fd.code_excerpt(_result(), ["https://a.test/"], "Line 10: Element x", 3)
    assert red["color"] == "red" and red["line"] == 10
    assert [number for number, _line, _marked in red["lines"]] == list(range(7, 14))
    assert [number for number, _line, marked in red["lines"] if marked] == [10]
    assert fd.code_excerpt(_result(), ["https://a.test/"], "Line 2: x", 2)["color"] == "yellow"
    assert fd.code_excerpt(_result(), ["https://a.test/"], "Line 2: x", 0)["color"] == "blue"
    assert fd.code_excerpt(_result(), ["https://a.test/"], "Line 1: x", 3)["lines"][0][0] == 1


def test_no_excerpt_without_a_line_a_stored_page_or_a_valid_line():
    assert fd.code_excerpt(_result(), ["https://a.test/"], "kein Hinweis", 3) is None
    assert fd.code_excerpt(_result(), ["https://b.test/"], "Line 3: x", 3) is None
    assert fd.code_excerpt(_result(), ["https://a.test/"], "Line 999: x", 3) is None
    assert fd.code_excerpt(None, ["https://a.test/"], "Line 3: x", 3) is None


def test_the_html_is_escaped_and_the_marked_line_is_colored():
    page = SimpleNamespace(url="https://a.test/", html="<script>alert(1)</script>\nzwei\n")
    result = SimpleNamespace(snapshot=SimpleNamespace(pages=[page]))
    excerpt = fd.code_excerpt(result, ["https://a.test/"], "Line 1: x", 3)
    html_text = fd.excerpt_html(excerpt, "de")
    assert "&lt;script&gt;" in html_text and "<script>" not in html_text
    assert fd.COLORS["red"] in html_text


def test_only_https_references_become_links():
    meta = SimpleNamespace(title="T", why="W", fix="F", method="M", logic="L",
                           refs=["https://example.test/a", "http://nope.test", "javascript:x"])
    groups = [{"check_id": "SEC-HDR-001", "severity": 2, "msg_de": "m", "msg_en": "m", "count": 1,
               "example_urls": ["https://a.test/x"], "evidence": "Line 3: <b>"}]
    result = fd.explain_html("SEC-HDR-001", groups, ["m"], "de", meta, _result())
    assert 'href="https://example.test/a"' in result and "nope.test" not in result and "javascript" not in result
    assert 'href="https://a.test/x"' in result and "&lt;b&gt;" in result
