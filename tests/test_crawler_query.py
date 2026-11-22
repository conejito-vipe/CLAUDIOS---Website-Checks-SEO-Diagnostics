"""Crawler: Query-Varianten (Joomla ?view=category&id=...) nur, wenn der Pfad sonst unbekannt ist."""
from __future__ import annotations

from urllib.parse import urlsplit

from claudios.core.crawler import crawl, has_paging
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Snapshot

HEADERS = {"content-type": "text/html; charset=utf-8"}


def html(*links):
    body = " ".join(f'<a href="{href}">x</a>' for href in links)
    return f'<!doctype html><html lang="en"><head><title>t</title></head><body>{body}</body></html>'


class FakeGK:
    cancel = None

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    async def fetch(self, url, **kw):
        self.calls.append(url)
        parts = urlsplit(url)
        if parts.path == "/robots.txt":
            return Response(url, 404, {}, [], b"", False, 1)
        return Response(url, 200, HEADERS, [], self.pages[parts.path].encode(), False, 1)


def new_snap():
    return Snapshot(target=normalize_input("example.com"), level=1, profile="standard")


def test_paging_keys_are_recognised():
    for query in ("start=1", "page=2", "Page=3&x=1", "limitstart=20", "seite=2"):
        assert has_paging(query), query
    for query in ("view=category&id=13", "format=xml", "x=1"):
        assert not has_paging(query), query


async def test_query_variants_of_known_paths_are_not_fetched():
    pages = {
        "/": html("/a", "/a?view=category&id=1", "/?view=category&id=2", "/list", "/list?start=1", "/only?x=1"),
        "/a": html("/"), "/list": html("/"), "/only": html("/"),
    }
    gk, snap = FakeGK(pages), new_snap()
    await crawl(gk, snap)
    assert sorted(p.url for p in snap.pages) == [
        "https://example.com/", "https://example.com/a", "https://example.com/list",
        "https://example.com/list?start=1", "https://example.com/only?x=1"]
    assert [s for s in snap.skipped if s["reason"] == "query_variant"] == [{"reason": "query_variant", "count": 2}]
    assert not [c for c in gk.calls if "view=category" in c]


async def test_no_query_entry_without_skipped_variants():
    pages = {"/": html("/a", "/b?x=1"), "/a": html("/"), "/b": html("/")}
    snap = new_snap()
    await crawl(FakeGK(pages), snap)
    assert len(snap.pages) == 3
    assert not [s for s in snap.skipped if s["reason"] == "query_variant"]
