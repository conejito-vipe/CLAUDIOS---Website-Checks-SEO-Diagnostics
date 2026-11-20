"""DNS über HTTPS ohne die Prüfung von dnspython: Ziel-IP, SNI, Host-Header, Fehlerfälle, Einschalten des Ersatzes."""
import dns.exception
import dns.message
import dns.query
import dns.rrset
import httpx
import pytest

from claudios.core import dohfallback


def test_the_query_goes_to_the_bootstrap_ip_with_sni_and_host_header():
    seen = {}

    def handler(request):
        seen.update(host=request.url.host, host_header=request.headers["host"],
                    sni=request.extensions.get("sni_hostname"), ctype=request.headers["content-type"])
        reply = dns.message.make_response(dns.message.from_wire(request.content))
        reply.answer.append(dns.rrset.from_text("example.com.", 300, "IN", "A", "93.184.216.34"))
        return httpx.Response(200, content=reply.to_wire())

    query = dns.message.make_query("example.com", "A")
    answer = dohfallback.https_query(query, "https://dns.quad9.net/dns-query", timeout=3, bootstrap_address="9.9.9.9",
                                     _transport=httpx.MockTransport(handler))
    assert [r.to_text() for rrset in answer.answer for r in rrset] == ["93.184.216.34"]
    assert seen == {"host": "9.9.9.9", "host_header": "dns.quad9.net", "sni": "dns.quad9.net",
                    "ctype": "application/dns-message"}


def test_errors_are_reported():
    query = dns.message.make_query("example.com", "A")
    bad = httpx.MockTransport(lambda request: httpx.Response(500))
    with pytest.raises(dns.exception.DNSException):
        dohfallback.https_query(query, "https://dns.quad9.net/dns-query", _transport=bad)
    huge = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 70000))
    with pytest.raises(dns.exception.DNSException):
        dohfallback.https_query(query, "https://dns.quad9.net/dns-query", _transport=huge)
    with pytest.raises(ValueError):
        dohfallback.https_query(query, "http://dns.quad9.net/dns-query")


def test_the_fallback_replaces_dnspython_only_when_needed(monkeypatch):
    original = dns.query.https
    monkeypatch.setattr(dns.query, "have_doh", True, raising=False)
    assert dohfallback.install_if_needed() == "native" and dns.query.https is original
    monkeypatch.setattr(dns.query, "have_doh", False, raising=False)
    monkeypatch.setattr(dns.query, "https", original)
    assert dohfallback.install_if_needed() == "fallback"
    assert dns.query.https is dohfallback.https_query
