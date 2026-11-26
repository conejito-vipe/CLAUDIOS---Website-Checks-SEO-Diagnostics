"""Sitemap- und Soft-404-Probe: Abbruch geht nach oben, Fremdhosts und http werden nie abgefragt, Grenzen gelten."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from claudios.core import seoprobe
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.limits import LIMITS

URLSET = "<?xml version='1.0'?><urlset>{}</urlset>"


def resp(status=200, body="", chain=(), url="https://example.com/"):
    return SimpleNamespace(status=status, body=body.encode(), chain=list(chain), url=url)


class GK:
    """Gatekeeper-Attrappe: antwortet je Adresse und Methode, zählt alle Anfragen."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def fetch(self, url, method="GET", max_bytes=0):
        self.calls.append((method, url))
        answer = self.routes.get((method, url), self.routes.get(url))
        if isinstance(answer, Exception):
            raise answer
        return answer if answer is not None else resp(404)


def snap(robots="", pages=()):
    page = SimpleNamespace(url="https://example.com/", chain=[])
    return SimpleNamespace(pages=[page, *pages], robots_txt=robots,
                           target=SimpleNamespace(registrable="example.com", host="example.com"))


async def test_cancel_and_byte_limit_errors_travel_up_but_other_errors_mean_unreachable():
    for code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
        with pytest.raises(ClaudiosError):
            await seoprobe._fetch(GK({"u": ClaudiosError(code)}), "u", 10)
        with pytest.raises(ClaudiosError):
            await seoprobe._status_of(GK({"u": ClaudiosError(code)}), "u")
    assert await seoprobe._fetch(GK({"u": ClaudiosError(E.TARGET_PRIVATE)}), "u", 10) is None
    rec = await seoprobe._status_of(GK({"u": ClaudiosError(E.TARGET_PRIVATE)}), "u")
    assert rec["error"] == E.TARGET_PRIVATE.value and rec["status"] is None


async def test_status_check_falls_back_from_head_to_get_only_when_head_is_unsupported():
    gk = GK({("HEAD", "u"): resp(405), ("GET", "u"): resp(200, chain=["a", "b"])})
    rec = await seoprobe._status_of(gk, "u")
    assert rec["status"] == 200 and rec["redirects"] == 2 and [m for m, _ in gk.calls] == ["HEAD", "GET"]
    gk = GK({("HEAD", "u"): resp(404)})
    assert (await seoprobe._status_of(gk, "u"))["status"] == 404 and len(gk.calls) == 1
    gk = GK({("HEAD", "u"): resp(501), ("GET", "u"): resp(501)})
    assert (await seoprobe._status_of(gk, "u"))["status"] == 501


async def test_a_declared_sitemap_is_used_and_the_default_is_tried_only_if_not_declared():
    robots = "Sitemap: https://example.com/map.xml\nSitemap: https://example.com/sitemap.xml\n"
    gk = GK({"https://example.com/map.xml": resp(200, URLSET.format("")), })
    data = await seoprobe.collect_sitemap(gk, snap(robots))
    assert data["found"] and data["declared"] and data["source"] == "https://example.com/map.xml"
    assert [u for _m, u in gk.calls] == ["https://example.com/map.xml"]  # nach dem ersten Treffer Schluss
    gk = GK({})
    data = await seoprobe.collect_sitemap(gk, snap("Sitemap: https://example.com/sitemap.xml"))
    assert not data["found"] and data["reachable"] and [u for _m, u in gk.calls] == ["https://example.com/sitemap.xml"]


async def test_a_sitemap_index_follows_only_the_first_child_and_a_broken_child_is_reported():
    index = "<sitemapindex><sitemap><loc>https://example.com/c1.xml</loc></sitemap><sitemap><loc>https://example.com/c2.xml</loc></sitemap></sitemapindex>"
    child = URLSET.format("<url><loc>https://example.com/a</loc></url>")
    gk = GK({"https://example.com/sitemap.xml": resp(200, index), "https://example.com/c1.xml": resp(200, child),
             ("HEAD", "https://example.com/a"): resp(200)})
    data = await seoprobe.collect_sitemap(gk, snap())
    assert data["index"] and data["total"] == 1 and not data["child_failed"]
    assert not any("c2.xml" in u for _m, u in gk.calls)
    gk = GK({"https://example.com/sitemap.xml": resp(200, index), "https://example.com/c1.xml": resp(500, "x")})
    assert (await seoprobe.collect_sitemap(gk, snap()))["child_failed"] is True
    empty = "<sitemapindex></sitemapindex>"
    assert (await seoprobe.collect_sitemap(GK({"https://example.com/sitemap.xml": resp(200, empty)}), snap()))["child_failed"]


async def test_only_https_urls_of_the_same_site_that_were_not_crawled_are_checked_and_never_more_than_the_limit(monkeypatch):
    locs = ["http://example.com/plain", "https://evil.net/x", "https://example.com/crawled", "https://shop.example.com/ok1",
            "https://example.com/ok2", "https://example.com/ok3"]
    body = URLSET.format("".join(f"<url><loc>{u}</loc></url>" for u in locs))
    routes = {"https://example.com/sitemap.xml": resp(200, body)}
    for u in locs:
        routes[("HEAD", u)] = resp(200)
    crawled = SimpleNamespace(url="https://example.com/crawled", chain=[])
    gk = GK(routes)
    data = await seoprobe.collect_sitemap(gk, snap(pages=[crawled]))
    asked = [u for m, u in gk.calls if m == "HEAD"]
    assert "http://example.com/plain" not in asked and "https://evil.net/x" not in asked
    assert "https://example.com/crawled" not in asked
    assert len(asked) <= LIMITS.sitemap_urls_checked and len(data["checked"]) == len(asked) and asked[0] == "https://shop.example.com/ok1"


async def test_soft_404_probe_asks_one_random_address_and_reports_the_answer_or_the_error():
    gk = GK({})
    gk.fetch_original = gk.fetch

    async def fetch(url, method="GET", max_bytes=0):
        gk.calls.append((method, url))
        return resp(200, "hallo", chain=["x"], url="https://example.com/home")

    gk.fetch = fetch
    rec = await seoprobe.probe_soft404(gk, snap())
    assert rec == {"status": 200, "error": None, "redirects": 1, "final": "https://example.com/home"}
    assert len(gk.calls) == 1 and gk.calls[0][1].startswith("https://example.com/claudios-check-")
    first = gk.calls[0][1]
    await seoprobe.probe_soft404(gk, snap())
    assert gk.calls[1][1] != first  # jedes Mal eine neue Zufallsadresse
    failing = GK({})

    async def boom(url, method="GET", max_bytes=0):
        raise ClaudiosError(E.TARGET_PRIVATE)

    failing.fetch = boom
    assert (await seoprobe.probe_soft404(failing, snap()))["error"] == E.TARGET_PRIVATE.value

    async def cancelled(url, method="GET", max_bytes=0):
        raise ClaudiosError(E.SCAN_CANCELLED)

    failing.fetch = cancelled
    with pytest.raises(ClaudiosError):
        await seoprobe.probe_soft404(failing, snap())
