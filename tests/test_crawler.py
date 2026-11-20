from urllib.parse import urlsplit

from claudios.core.crawler import crawl
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Snapshot


def page_html(links):
    return ("<html><body>" + "".join(f'<a href="{x}">x</a>' for x in links) + "</body></html>").encode()


class FakeGatekeeper:
    """Ersetzt das Netzwerk: liefert eine kleine künstliche Website."""

    def __init__(self, site, robots=None):
        self.site, self.robots, self.calls = site, robots, []

    async def fetch(self, url, **kw):
        self.calls.append(url)
        path = urlsplit(url).path
        if path == "/robots.txt":
            if self.robots is None:
                return Response(url, 404, {}, [], b"", False, 1)
            return Response(url, 200, {"content-type": "text/plain"}, [], self.robots.encode(), False, 1)
        links = self.site(path)
        return Response(url, 200, {"content-type": "text/html; charset=utf-8"}, [], page_html(links), False, 1)


def make_snap(level=1):
    return Snapshot(target=normalize_input("example.com"), level=level, profile="standard")


async def test_depth_is_limited_to_six_levels_and_robots_and_external_links_are_respected():
    def site(path):
        if path == "/":
            return ["/a1", "/private/x", "https://other.example/y"]
        if path.startswith("/a"):
            return [f"/a{int(path[2:]) + 1}"]
        return []

    gk = FakeGatekeeper(site, robots="User-agent: *\nDisallow: /private")
    snap = make_snap()
    await crawl(gk, snap)
    paths = [urlsplit(p.url).path for p in snap.pages]
    assert paths == ["/", "/a1", "/a2", "/a3", "/a4", "/a5"]  # Ebene 1 bis 6
    assert max(p.depth for p in snap.pages) == 6
    assert any(s["reason"] == "robots" for s in snap.skipped)
    assert not any("private" in c or "other.example" in c for c in gk.calls if not c.endswith("robots.txt"))


async def test_missing_robots_txt_does_not_block_crawling():
    gk = FakeGatekeeper(lambda path: ["/a"] if path == "/" else [], robots=None)
    snap = make_snap()
    await crawl(gk, snap)
    assert len(snap.pages) == 2


async def test_page_limit_for_level_1_is_250():
    gk = FakeGatekeeper(lambda path: [f"/p{i}" for i in range(300)] if path == "/" else [])
    snap = make_snap(level=1)
    await crawl(gk, snap)
    assert len(snap.pages) == 250
    assert any(s["reason"] == "page_limit" for s in snap.skipped)
