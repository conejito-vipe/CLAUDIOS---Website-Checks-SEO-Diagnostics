"""Externe Links ohne Weiterleitungen: 3xx wird gespeichert, aber nicht als kaputter Link gemeldet."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from claudios.core import linkprobe
from claudios.core.engine import run_checks
from claudios.core.errors import ErrorCode as E
from claudios.core.guard import normalize_input
from claudios.core.linkprobe import check_external_links
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot


def make_snap(links):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html="<html></html>",
                           content_type="text/html", external_links=list(links)))
    return snap


class FakeGK:
    cancel = None

    def __init__(self, status_by_path, slow_hosts=()):
        self.status_by_path, self.slow_hosts, self.calls = status_by_path, set(slow_hosts), []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        self.calls.append((method, url, follow))
        parts = urlsplit(url)
        if parts.hostname in self.slow_hosts:
            await asyncio.sleep(5)
        return Response(url, self.status_by_path.get(parts.path, 200), {}, [], b"", False, 1)


async def test_redirects_are_stored_but_not_reported():
    links = ["https://ext.example/moved", "https://ext.example/temp", "https://ext.example/gone",
             "https://ext.example/ok"]
    snap = make_snap(links)
    gk = FakeGK({"/moved": 301, "/temp": 302, "/gone": 404})
    data = await check_external_links(gk, snap)
    by_url = {r["url"]: r for r in data["results"]}
    assert by_url["https://ext.example/moved"]["status"] == 301
    assert by_url["https://ext.example/moved"]["redirects"] == 1
    assert by_url["https://ext.example/temp"]["status"] == 302
    assert by_url["https://ext.example/ok"]["redirects"] == 0
    assert all(call[2] is False for call in gk.calls)
    snap.extra["links"] = data
    findings, _ = run_checks(snap, 1, "standard")
    ext = [f for f in findings if f.check_id == "LNK-EXT-001"]
    assert len(ext) == 1 and "404" in ext[0].msg_en


async def test_slow_host_is_skipped_after_two_timeouts(monkeypatch):
    monkeypatch.setattr(linkprobe, "LINK_TIMEOUT", 0.05)
    links = [f"https://slow.example/p{i}" for i in range(4)] + ["https://fast.example/ok"]
    gk = FakeGK({}, slow_hosts={"slow.example"})
    data = await check_external_links(gk, make_snap(links))
    by_url = {r["url"]: r for r in data["results"]}
    for i in range(4):
        assert by_url[f"https://slow.example/p{i}"]["error"] == E.NET_TIMEOUT.value
    assert by_url["https://fast.example/ok"]["status"] == 200
    assert data["skipped_hosts"] == 2 and data["checked"] == 5
    assert len([c for c in gk.calls if "slow.example" in c[1]]) == 2
