"""Crawler: Seiten, die nach einer Weiterleitung auf eine schon gecrawlte Adresse führen, zählen nicht doppelt."""
from __future__ import annotations

from urllib.parse import urlsplit

from claudios.core.crawler import crawl
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
        if parts.path.startswith("/old"):  # alte Adresse: Weiterleitung auf /a
            return Response("https://example.com/a", 200, HEADERS, [url], self.pages["/a"].encode(), False, 1)
        return Response(url, 200, HEADERS, [], self.pages[parts.path].encode(), False, 1)


def new_snap():
    return Snapshot(target=normalize_input("example.com"), level=1, profile="standard")


async def test_redirect_duplicates_are_not_counted_twice():
    pages = {"/": html("/a", "/old1", "/old2", "/b"), "/a": html("/"), "/b": html("/a")}
    gk, snap = FakeGK(pages), new_snap()
    await crawl(gk, snap)
    assert sorted(p.url for p in snap.pages) == ["https://example.com/", "https://example.com/a",
                                                  "https://example.com/b"]
    assert [s for s in snap.skipped if s["reason"] == "duplicate"] == [{"reason": "duplicate", "count": 2}]
    assert gk.calls.count("https://example.com/a") == 1


async def test_no_duplicate_entry_without_duplicates():
    pages = {"/": html("/a", "/b"), "/a": html("/"), "/b": html("/a")}
    snap = new_snap()
    await crawl(FakeGK(pages), snap)
    assert len(snap.pages) == 3
    assert not [s for s in snap.skipped if s["reason"] == "duplicate"]
