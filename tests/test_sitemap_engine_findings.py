"""Sitemap- und Browser-Vergleich-Befunde: jeder Zweig der aufgeteilten Prüffunktionen einzeln (ohne Netz)."""
from __future__ import annotations

from claudios.checks import enginechecks, seo_more
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot

HOME = "https://example.com/"


def page(url, status=200, html="<html><head><title>x</title></head></html>", chain=(), headers=None):
    return Page(url=url, depth=1, status=status, html=html, content_type="text/html", chain=list(chain),
                headers=headers or {})


def snap_with(pages, sitemap=None, engines=None):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.extend(pages)
    snap.status = "complete"
    if sitemap is not None:
        snap.extra["sitemap"] = {"found": True, "reachable": True, "declared": True, "urls": [HOME], "checked": [],
                                 "index": False, "truncated": False, "child_failed": False} | sitemap
    if engines is not None:
        snap.extra["engines"] = engines
    return snap


def msgs(found, severity=None):
    return [f.msg_en for f in found if severity is None or f.severity == severity]


def test_addresses_without_https_and_from_another_domain_are_reported_with_an_example():
    snap = snap_with([page(HOME)], {"urls": [HOME, "http://example.com/a", "https://other.net/b"]})
    found = seo_more.sitemap(snap)
    assert ("1 sitemap address(es) without HTTPS", S.WARNING) in {(f.msg_en, f.severity) for f in found}
    assert any(f.msg_en.startswith("2 sitemap address(es) of another domain") or "of another domain" in f.msg_en
               for f in found)
    assert not any("without HTTPS" in m for m in msgs(seo_more.sitemap(snap_with([page(HOME)], {}))))


def test_a_listed_page_with_an_error_a_redirect_or_noindex_is_reported_once_each():
    pages = [page(HOME + "gone", status=404), page(HOME + "target", chain=[HOME + "old"]),
             page(HOME + "hidden", html='<html><head><meta name="robots" content="noindex"></head></html>')]
    urls = [HOME + "gone", HOME + "old", HOME + "hidden"]
    found = seo_more.sitemap(snap_with(pages, {"urls": urls}))
    assert (S.ERROR, "Sitemap address returns HTTP 404") in {(f.severity, f.msg_en) for f in found}
    assert (S.NOTE, "Sitemap address redirects") in {(f.severity, f.msg_en) for f in found}
    assert (S.WARNING, "Sitemap contains a noindex page") in {(f.severity, f.msg_en) for f in found}
    unrelated = seo_more.sitemap(snap_with([page(HOME + "elsewhere", status=500)], {"urls": [HOME + "x"]}))
    assert not any("returns HTTP 500" in m for m in msgs(unrelated))  # nicht gelistete Seiten gehören nicht dazu


def test_probed_sitemap_addresses_give_error_warning_or_note():
    checked = [{"url": HOME + "a", "error": "timeout", "status": None, "redirects": 0},
               {"url": HOME + "b", "error": None, "status": 410, "redirects": 0},
               {"url": HOME + "c", "error": None, "status": 200, "redirects": 1},
               {"url": HOME + "d", "error": None, "status": 200, "redirects": 0}]
    found = seo_more._sitemap_probe_findings(checked)
    assert [(f.severity, f.url) for f in found] == [(S.WARNING, HOME + "a"), (S.ERROR, HOME + "b"), (S.NOTE, HOME + "c")]


def test_crawled_indexable_pages_missing_from_the_sitemap_are_counted_but_not_for_an_index():
    pages = [page(HOME), page(HOME + "new"), page(HOME + "q?x=1"), page(HOME + "off", html=(
        '<html><head><meta name="robots" content="noindex"></head></html>')), page(HOME + "err", status=404)]
    found = seo_more.sitemap(snap_with(pages, {"urls": [HOME]}))
    missing = [f for f in found if "missing from the sitemap" in f.msg_en]
    assert len(missing) == 1 and missing[0].msg_en.startswith("1 crawled page(s)") and missing[0].url == HOME + "new"
    assert seo_more._sitemap_missing_findings(snap_with([page(HOME)]), {HOME.lower()}) == []  # alles gelistet
    assert not [f for f in seo_more.sitemap(snap_with(pages, {"urls": [HOME], "index": True}))
                if "missing from the sitemap" in f.msg_en]
    assert not [f for f in seo_more.sitemap(snap_with(pages, {"urls": [HOME], "truncated": True}))
                if "missing from the sitemap" in f.msg_en]


def test_empty_or_undeclared_sitemaps_and_failed_child_sitemaps():
    assert msgs(seo_more.sitemap(snap_with([], {"urls": []})), S.WARNING) == ["The sitemap contains no addresses"]
    assert msgs(seo_more.sitemap(snap_with([], {"urls": [], "child_failed": True})), S.NOTE) == [
        "Sitemap index: the child sitemap is not reachable"]
    assert "Sitemap is not listed in robots.txt" in msgs(seo_more.sitemap(snap_with([page(HOME)], {"declared": False})))


def _eng(pages, engine="firefox", error=None):
    return {"engines": [{"engine": engine, "pages": pages, "error": error}]}


def _chromium(snap_pages):
    return {"pages": snap_pages}


def test_browser_differences_compare_with_the_chromium_run(monkeypatch):
    monkeypatch.setattr(enginechecks, "_baseline", lambda snap: {HOME: {"url": HOME, "page_errors": [], "overflow": {}},
                                                                  HOME + "b": {"url": HOME + "b", "error": "x"}})
    pages = [{"url": HOME, "error": "net::ERR", "page_errors": [], "overflow": {}},
             {"url": HOME + "b", "error": "net::ERR"},
             {"url": HOME + "c", "page_errors": ["boom"], "overflow": {"360": True}},
             {"url": HOME, "page_errors": ["boom1", "boom2"], "overflow": {"360": True}},
             {"url": HOME, "error": "offsite_redirect"}, "kein-dict"]
    found = enginechecks.engine_differences(snap_with([], engines=_eng(pages)))
    assert [(f.severity, f.url) for f in found] == [
        (S.WARNING, HOME),  # lädt in Chromium, nicht in Firefox
        (S.NOTE, HOME + "b"),  # lädt auch in Chromium nicht
        (S.NOTE, HOME), (S.NOTE, HOME)]  # nur hier: Ausnahmen und Überlauf der vierten Seite
    assert "(in Chromium schon)" in found[0].msg_de and "2 JavaScript exception(s) only in Firefox" in found[2].msg_en
    assert "Horizontal scrolling at 360 px only in Firefox" in found[3].msg_en


def test_an_engine_that_does_not_start_is_an_info_and_total_failure_is_skipped():
    found = enginechecks.engine_differences(snap_with([], engines={"engines": [
        {"engine": "webkit", "pages": [], "error": "x"}, {"engine": "firefox", "pages": [
            {"url": HOME, "page_errors": [], "overflow": {}}]}]}))
    assert [(f.severity, f.msg_en) for f in found] == [(S.INFO, "WebKit could not be started")]
    try:
        enginechecks.engine_differences(snap_with([], engines={"engines": [{"engine": "webkit", "pages": [],
                                                                           "error": "x"}]}))
    except enginechecks.CheckSkipped as skip:
        assert str(skip) == "engines_failed"
    else:
        raise AssertionError("keine Übersprungen-Meldung")
