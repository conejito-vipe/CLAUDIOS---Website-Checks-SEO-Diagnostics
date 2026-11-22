"""norm(): Umlaute und Prozent-Kodierung gelten als dieselbe Adresse."""
from __future__ import annotations

from urllib.parse import unquote, urlsplit

from claudios.core.crawler import crawl, norm
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Snapshot

HEADERS = {"content-type": "text/html; charset=utf-8"}


def test_norm_unifies_umlaut_and_percent_encoding():
    encoded = "https://example.com/rechtsanspr%C3%BCche/x"
    assert norm("https://Example.com/rechtsansprüche/x") == encoded
    assert norm(encoded) == encoded
    assert norm("https://example.com/a%c3%bcb") == "https://example.com/a%C3%BCb"
    assert norm("https://example.com/p?q=ü") == "https://example.com/p?q=%C3%BC"


def test_norm_keeps_encoded_slash_and_plain_addresses():
    assert norm("https://example.com/a%2Fb?x=1&y=%2f") == "https://example.com/a%2Fb?x=1&y=%2F"
    assert norm("https://example.com") == "https://example.com/"
    assert norm("https://example.com/a/b?x=1") == "https://example.com/a/b?x=1"


class FakeGK:
    cancel = None

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    async def fetch(self, url, **kw):
        self.calls.append(url)
        path = unquote(urlsplit(url).path)
        if path == "/robots.txt":
            return Response(url, 404, {}, [], b"", False, 1)
        return Response(url, 200, HEADERS, [], self.pages[path].encode("utf-8"), False, 1)


async def test_crawler_counts_umlaut_and_encoded_link_once():
    home = '<html><body><a href="/rüche">a</a> <a href="/r%C3%BCche">b</a></body></html>'
    gk = FakeGK({"/": home, "/rüche": "<html><body>x</body></html>"})
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    await crawl(gk, snap)
    assert sorted(p.url for p in snap.pages) == ["https://example.com/", "https://example.com/r%C3%BCche"]
    assert len([c for c in gk.calls if "robots" not in c]) == 2
