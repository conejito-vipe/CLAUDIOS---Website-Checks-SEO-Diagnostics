"""TLS-Handshake zur öffentlichen IP: Restlaufzeit, Aussteller, Wechsel der Adresse, Fehlerarten (ohne Netz, mit Attrappen)."""
from __future__ import annotations

import ssl
from types import SimpleNamespace

import pytest

from claudios.core import tlsprobe
from claudios.core.errors import ClaudiosError, ErrorCode as E

NOT_AFTER = "Jan  1 00:00:00 2031 GMT"
EXPIRES = ssl.cert_time_to_seconds(NOT_AFTER)


class Conn:
    def __init__(self, ip):
        self.ip = ip

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class Tls(Conn):
    def __init__(self, ip, cert, version="TLSv1.3", cipher=("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)):
        super().__init__(ip)
        self.cert, self._version, self._cipher = cert, version, cipher

    def getpeercert(self):
        return self.cert

    def version(self):
        return self._version

    def cipher(self):
        return self._cipher

    def selected_alpn_protocol(self):
        return "h2"


@pytest.fixture
def net(monkeypatch):
    """Attrappe für Verbindung und TLS. state['fail'] = Adressen, bei denen die Verbindung scheitert."""
    state = {"fail": {}, "tried": [], "cert": None, "ctx": None}

    def create_connection(address, timeout):
        ip = address[0]
        state["tried"].append(ip)
        if ip in state["fail"]:
            raise state["fail"][ip]
        return Conn(ip)

    class Ctx:
        minimum_version = None

        def set_alpn_protocols(self, protocols):
            self.alpn = protocols

        def wrap_socket(self, raw, server_hostname):
            state["host"] = server_hostname
            return Tls(raw.ip, state["cert"])

    def make_ctx():
        state["ctx"] = Ctx()
        return state["ctx"]

    state["cert"] = {"notAfter": NOT_AFTER, "issuer": ((("organizationName", "Beispiel CA"),),)}
    monkeypatch.setattr(tlsprobe.socket, "create_connection", create_connection)
    monkeypatch.setattr(tlsprobe.ssl, "create_default_context", make_ctx)
    monkeypatch.setattr(tlsprobe, "time", SimpleNamespace(time=lambda: EXPIRES - 90 * 86400 - 100))
    return state


def test_successful_handshake_reports_days_left_issuer_and_protocol(net):
    result = tlsprobe._handshake("example.com", ["93.184.216.34"])
    assert result == {"version": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384", "days_left": 90,
                      "issuer": "Beispiel CA", "error": None, "alpn": "h2", "san": []}
    assert net["host"] == "example.com"  # Zertifikat wird gegen den Namen geprüft, nicht gegen die IP
    assert net["ctx"].minimum_version == ssl.TLSVersion.TLSv1_2  # alte Protokolle prüft später sslyze


def test_issuer_falls_back_to_the_common_name_and_then_to_empty(net):
    net["cert"] = {"notAfter": NOT_AFTER, "issuer": ((("commonName", "Nur Name"),),)}
    assert tlsprobe._handshake("example.com", ["1.2.3.4"])["issuer"] == "Nur Name"
    net["cert"] = {"notAfter": NOT_AFTER}
    assert tlsprobe._handshake("example.com", ["1.2.3.4"])["issuer"] == ""


def test_expired_certificate_has_negative_days_left(net, monkeypatch):
    monkeypatch.setattr(tlsprobe, "time", SimpleNamespace(time=lambda: EXPIRES + 3 * 86400 + 10))
    assert tlsprobe._handshake("example.com", ["1.2.3.4"])["days_left"] == -4  # abgerundet: 3 Tage und 10 s darüber


def test_next_address_is_tried_when_the_first_one_fails(net):
    net["fail"] = {"10.0.0.1": ConnectionRefusedError()}
    result = tlsprobe._handshake("example.com", ["10.0.0.1", "10.0.0.2"])
    assert result["error"] is None and net["tried"] == ["10.0.0.1", "10.0.0.2"]


def test_at_most_three_addresses_are_tried_and_the_last_error_is_named(net):
    net["fail"] = {f"10.0.0.{i}": ssl.SSLError("kaputt") if i == 3 else TimeoutError() for i in range(1, 6)}
    result = tlsprobe._handshake("example.com", [f"10.0.0.{i}" for i in range(1, 6)])
    assert net["tried"] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    assert result == {"error": "SSLError"}


def test_no_address_is_reported_without_a_connection(net):
    assert tlsprobe._handshake("example.com", []) == {"error": "no address"}
    assert net["tried"] == []


def _snap():
    return SimpleNamespace(target=SimpleNamespace(host="example.com"))


async def test_probe_resolves_first_and_returns_the_handshake(net, monkeypatch):
    async def resolve(_resolver, host, allow_loopback):
        assert host == "example.com" and allow_loopback is False  # lokale Ziele gibt es hier nie
        return ["93.184.216.34"]

    monkeypatch.setattr(tlsprobe, "resolve_public", resolve)
    result = await tlsprobe.probe_tls(object(), _snap())
    assert result["error"] is None and result["days_left"] == 90 and net["tried"] == ["93.184.216.34"]


async def test_probe_returns_the_error_code_for_a_private_target(net, monkeypatch):
    async def resolve(*_args):
        raise ClaudiosError(E.TARGET_PRIVATE, host="example.com")

    monkeypatch.setattr(tlsprobe, "resolve_public", resolve)
    assert await tlsprobe.probe_tls(object(), _snap()) == {"error": E.TARGET_PRIVATE.value}
    assert net["tried"] == []  # kein Verbindungsversuch zu einer privaten Adresse


async def test_probe_survives_a_certificate_without_expiry(net, monkeypatch):
    async def resolve(*_args):
        return ["93.184.216.34"]

    net["cert"] = {"issuer": ()}
    monkeypatch.setattr(tlsprobe, "resolve_public", resolve)
    assert await tlsprobe.probe_tls(object(), _snap()) == {"error": "KeyError"}
