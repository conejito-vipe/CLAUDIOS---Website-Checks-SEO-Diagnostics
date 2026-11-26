"""Netzwerk-Gatekeeper: Weiterleitungen, IP-Pinning, Größen- und Zeitgrenzen, Abbruch (ohne Netz, mit httpx.MockTransport)."""
from __future__ import annotations

import asyncio
import dataclasses

import httpx
import pytest

from claudios.core import net
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.guard import Target


class Resolver:
    """Löst Namen auf feste Adressen auf; unbekannte Namen zeigen auf eine öffentliche Adresse."""

    def __init__(self, table=None):
        self.table, self.asked = table or {}, []

    async def addresses(self, host):
        self.asked.append(host)
        return self.table.get(host, ["93.184.216.34"])


class Site:
    """Eine Attrappe des Netzes: antwortet je Pfad; zeichnet jede Anfrage auf."""

    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        reply = self.routes.get(request.url.path, httpx.Response(404))
        return reply(request) if callable(reply) else reply


def make(routes, resolver=None, host="example.com", allow_localhost=False, cancel=None):
    site = Site(routes)
    target = Target(url=f"https://{host}/", host=host, registrable="example.com", loopback=False)
    gate = net.Gatekeeper(target, resolver=resolver or Resolver(), allow_localhost=allow_localhost, cancel=cancel)
    gate._client = httpx.AsyncClient(transport=httpx.MockTransport(site), follow_redirects=False)
    gate._interval = 0  # kein künstliches Warten im Test
    return gate, site


def redirect(to, status=302):
    return httpx.Response(status, headers={"location": to})


async def test_request_goes_to_the_checked_ip_with_the_original_host_name():
    gate, site = make({"/": httpx.Response(200, text="ok")})
    resp = await gate.fetch("https://example.com/")
    request = site.seen[0]
    assert request.url.host == "93.184.216.34"  # IP-Pinning: nur die geprüfte Adresse wird angesprochen
    assert request.headers["host"] == "example.com" and request.extensions["sni_hostname"] == "example.com"
    assert resp.body == b"ok" and resp.status == 200


async def test_a_host_that_resolves_to_a_private_address_is_never_contacted():
    gate, site = make({"/": httpx.Response(200)}, resolver=Resolver({"example.com": ["93.184.216.34", "10.0.0.5"]}))
    with pytest.raises(ClaudiosError) as err:  # eine einzige private Adresse genügt (DNS-Rebinding-Schutz)
        await gate.fetch("https://example.com/")
    assert err.value.code == E.TARGET_PRIVATE and site.seen == []


async def test_redirect_to_a_foreign_site_is_reported_but_not_followed():
    gate, site = make({"/": redirect("https://evil.example.net/x")})
    resp = await gate.fetch("https://example.com/")
    assert resp.blocked_redirect == "https://evil.example.net/x" and len(site.seen) == 1


async def test_redirect_to_http_is_a_downgrade_and_not_followed():
    gate, site = make({"/": redirect("http://example.com/plain")})
    resp = await gate.fetch("https://example.com/")
    assert resp.downgrade and resp.blocked_redirect == "http://example.com/plain" and len(site.seen) == 1


async def test_redirect_inside_the_site_is_followed_and_the_chain_is_kept():
    gate, site = make({"/": redirect("/a"), "/a": httpx.Response(200, text="end")})
    resp = await gate.fetch("https://example.com/")
    assert resp.body == b"end" and resp.chain == ["https://example.com/"] and len(site.seen) == 2


async def test_redirect_to_a_sub_domain_with_a_private_address_is_stopped():
    resolver = Resolver({"intern.example.com": ["192.168.1.10"]})
    gate, site = make({"/": redirect("https://intern.example.com/")}, resolver=resolver)
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == E.TARGET_PRIVATE and len(site.seen) == 1


async def test_redirect_loops_and_endless_chains_end_with_an_error():
    gate, _ = make({"/": redirect("/a"), "/a": redirect("/")})
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == E.NET_REDIRECTS
    chain = {f"/{i}": redirect(f"/{i + 1}") for i in range(50)} | {"/": redirect("/0")}
    gate, site = make(chain)
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == E.NET_REDIRECTS and len(site.seen) <= net.LIMITS.max_redirects + 2


@pytest.mark.parametrize("url,code", [
    ("https://user:pw@example.com/", E.INPUT_CREDENTIALS),
    ("http://example.com/", E.NET_DOWNGRADE),
    ("https://example.com:8443/", E.INPUT_INVALID),
    ("https://other-site.net/", E.NET_CROSS_SITE),
    ("ftp://example.com/", E.NET_DOWNGRADE),
])
async def test_forbidden_addresses_are_refused_before_any_request(url, code):
    gate, site = make({"/": httpx.Response(200)})
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch(url)
    assert err.value.code == code and site.seen == []


async def test_only_get_and_head_are_allowed():
    gate, site = make({"/": httpx.Response(200)})
    for method in ("POST", "PUT", "DELETE", "get"):
        with pytest.raises(ClaudiosError):
            await gate.fetch("https://example.com/", method=method)
    assert site.seen == []
    assert (await gate.fetch("https://example.com/", method="HEAD")).body == b""


async def test_large_answers_are_cut_at_the_limit_and_marked():
    gate, _ = make({"/": httpx.Response(200, content=b"x" * 10_000)})
    resp = await gate.fetch("https://example.com/", max_bytes=100)
    assert len(resp.body) == 100 and resp.truncated
    small = await gate.fetch("https://example.com/", max_bytes=20_000)
    assert len(small.body) == 10_000 and not small.truncated


async def test_the_total_volume_of_a_scan_is_limited(monkeypatch):
    monkeypatch.setattr(net, "LIMITS", dataclasses.replace(net.LIMITS, max_scan_bytes=150))
    gate, _ = make({"/": httpx.Response(200, content=b"x" * 100)})
    await gate.fetch("https://example.com/")
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == E.LIMIT_BYTES


async def test_secrets_in_answers_are_masked_and_session_headers_are_dropped():
    reply = httpx.Response(200, headers=[("set-cookie", "sid=abc; Secure"), ("x-debug", "token=supersecretvalue1"),
                                         ("authorization", "Bearer abcdefghijklmnop")])
    gate, _ = make({"/": reply})
    resp = await gate.fetch("https://example.com/")
    assert "set-cookie" not in resp.headers and "authorization" not in resp.headers
    assert "supersecretvalue1" not in resp.headers["x-debug"] and len(resp.cookies) == 1


async def test_a_cancelled_scan_sends_no_further_request():
    cancel = asyncio.Event()
    cancel.set()
    gate, site = make({"/": httpx.Response(200)}, cancel=cancel)
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == E.SCAN_CANCELLED and site.seen == []


@pytest.mark.parametrize("exc,code", [(httpx.ReadTimeout("zu langsam"), E.NET_TIMEOUT),
                                      (httpx.ConnectError("weg"), E.NET_CONNECT)])
async def test_network_errors_become_clear_error_codes(exc, code):
    def boom(_request):
        raise exc

    gate, _ = make({"/": boom})
    with pytest.raises(ClaudiosError) as err:
        await gate.fetch("https://example.com/")
    assert err.value.code == code
