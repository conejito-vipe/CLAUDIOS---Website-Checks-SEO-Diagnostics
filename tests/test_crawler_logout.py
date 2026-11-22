"""Crawler: Abmelde-Adressen werden nicht abgerufen."""
from __future__ import annotations

from urllib.parse import urlsplit

from claudios.core.crawler import crawl, is_logout
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


def test_logout_urls_are_recognised():
    for path in ("/log-out", "/logout", "/user/logout/", "/Abmelden", "/konto/sign-out"):
        assert is_logout(path), path
    assert is_logout("/index.php", "task=user.logout")
    for path in ("/", "/blog", "/logout-faq-seite", "/log"):
        assert not is_logout(path), path


async def test_crawler_does_not_fetch_logout_links():
    pages = {"/": html("/a", "/log-out", "/index.php?task=user.logout"), "/a": html("/")}
    gk = FakeGK(pages)
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    await crawl(gk, snap)
    assert sorted(p.url for p in snap.pages) == ["https://example.com/", "https://example.com/a"]
    assert not [c for c in gk.calls if "log-out" in c or "logout" in c]
