"""Sitemap-Einträge: normale und CDATA-Schreibweise (manche CMS schreiben <loc><![CDATA[...]]></loc>)."""
from __future__ import annotations

from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.seoprobe import _locs, collect_sitemap
from claudios.core.snapshot import Page, Snapshot

XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<?xml-stylesheet type="text/xsl" href="/sitemap?view=xsl"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    '<url><loc><![CDATA[https://example.com/]]></loc></url>'
    '<url><loc><![CDATA[https://example.com/a]]></loc><lastmod>2026-03-04</lastmod></url>'
    '<url><loc>\n  <![CDATA[https://example.com/b?x=1&y=2]]>\n</loc></url>'
    '</urlset>'
)


def test_locs_reads_plain_cdata_and_mixed_entries():
    assert _locs("<loc>https://example.com/p?a=1&amp;b=2</loc>") == ["https://example.com/p?a=1&b=2"]
    assert _locs("<loc><![CDATA[https://example.com/x]]></loc>") == ["https://example.com/x"]
    mixed = "<loc> https://example.com/1 </loc><loc><![CDATA[https://example.com/2]]></loc>"
    assert _locs(mixed) == ["https://example.com/1", "https://example.com/2"]


def test_locs_unescapes_amp_in_cdata_and_ignores_empty_entries():
    assert _locs("<loc><![CDATA[https://example.com/q?a=1&amp;b=2]]></loc>") == ["https://example.com/q?a=1&b=2"]
    assert _locs("<loc></loc><loc><![CDATA[]]></loc><loc>   </loc>") == []


class FakeGK:
    cancel = None

    def __init__(self):
        self.calls = []

    async def fetch(self, url, **kw):
        self.calls.append(url)
        if url.endswith("/sitemap"):
            return Response(url, 200, {"content-type": "application/xml"}, [], XML.encode(), False, 1)
        return Response(url, 200, {}, [], b"", False, 1)


async def test_collect_sitemap_finds_cdata_urls_and_checks_the_uncrawled_ones():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html="<html></html>",
                           content_type="text/html"))
    snap.robots_txt = "User-agent: *\nSitemap: https://example.com/sitemap\n"
    data = await collect_sitemap(FakeGK(), snap)
    assert data["found"] and data["declared"] and data["total"] == 3
    assert data["urls"][0] == "https://example.com/"
    assert {rec["url"] for rec in data["checked"]} == {"https://example.com/a", "https://example.com/b?x=1&y=2"}
