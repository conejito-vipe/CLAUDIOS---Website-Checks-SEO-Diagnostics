"""Zertifikats-Logs (crt.sh): Schalter aus als Standard, Probe über den Gatekeeper, defensives Parsen, Check."""
# ruff: noqa: F811
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_ai_services import FakeGK, env, qapp, run, snap_of  # noqa: F401

from claudios.core import probe_ct, services
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.net import Response
from claudios.i18n.strings import TEXTS, get_lang, set_lang


def row(names, issuer="C=US, O=Let's Encrypt, CN=R11", days=2):
    return {"name_value": "\n".join(names), "issuer_name": issuer,
            "not_before": (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")}


def body(rows):
    return json.dumps(rows).encode()


def test_the_service_is_known_and_off_by_default(env):
    assert "crtsh" in services.KNOWN and services.enabled("crtsh") is False


async def test_the_probe_sends_nothing_while_the_switch_is_off(env):
    gk = FakeGK({})
    assert await probe_ct.collect(gk, snap_of(), None) == {"enabled": False, "skip": "ct_disabled"}
    assert gk.calls == []


async def test_the_probe_asks_crtsh_once_with_only_the_registrable_domain(env):
    services.set_enabled("crtsh", True)
    rows = [row(["example.com", "*.example.com", "admin.example.com", "evil.com", "x.example.com.evil.com"]),
            row(["vpn.example.com"], issuer="C=US, O=Other CA, CN=X")]
    gk = FakeGK({("crt.sh", "/"): (200, "application/json", body(rows))})
    data = await probe_ct.collect(gk, snap_of(), None)
    assert gk.calls == [("crt.sh", "/", True)]
    assert data["hosts"] == ["admin.example.com", "example.com", "vpn.example.com"]
    assert data["recent_issuers"] == {"Let's Encrypt": 1, "Other CA": 1} and probe_ct.MIN_LEVEL == 1


@pytest.mark.parametrize("resp,reason", [((500, "text/html", b""), "ct_http_500"),
                                         ((200, "application/json", b"["), "ct_unreadable"),
                                         ((200, "application/json", b'{"a": 1}'), "ct_unreadable")])
async def test_failures_become_a_reason(env, resp, reason):
    services.set_enabled("crtsh", True)
    assert (await probe_ct.collect(FakeGK({("crt.sh", "/"): resp}), snap_of(), None))["skip"] == reason


async def test_a_network_error_becomes_a_reason_but_cancel_goes_up(env):
    services.set_enabled("crtsh", True)

    class Down:
        def __init__(self, code):
            self.code = code

        async def fetch(self, *a, **k):
            raise ClaudiosError(self.code)

    assert (await probe_ct.collect(Down(E.NET_TIMEOUT), snap_of(), None))["skip"] == "ct_unreachable"
    with pytest.raises(ClaudiosError):
        await probe_ct.collect(Down(E.SCAN_CANCELLED), snap_of(), None)


async def test_a_truncated_answer_is_not_used(env):
    services.set_enabled("crtsh", True)

    class Big(FakeGK):
        async def fetch(self, url, **kw):
            return Response(url, 200, {}, [], b"[", True, 1)

    assert (await probe_ct.collect(Big({}), snap_of(), None))["skip"] == "ct_too_large"


def test_the_parser_ignores_foreign_names_and_junk():
    data = probe_ct.parse_rows([1, "x", {"name_value": 5}, row(["a.example.com", "bad host.example.com",
                                                              "notexample.com"])], "example.com")
    assert data["hosts"] == ["a.example.com"]
    with pytest.raises(ValueError):
        probe_ct.parse_rows({}, "example.com")


def test_the_parser_caps_hosts():
    rows = [row([f"h{i}.example.com" for i in range(800)])]
    assert len(probe_ct.parse_rows(rows, "example.com")["hosts"]) == 500


def test_the_check_is_skipped_without_the_switch_and_never_passes():
    snap = snap_of()
    snap.extra["ct"] = {"enabled": False, "skip": "ct_disabled"}
    found, state = run(snap, "SEC-CTL-001")
    assert found == [] and state.startswith("skipped")


def test_the_check_reports_internal_names_and_issuer_changes():
    snap = snap_of()
    snap.extra["ct"] = {"enabled": True, "skip": None, "hosts": ["www.example.com", "staging.example.com", "vpn.example.com"],
                        "recent_issuers": {"A": 1, "B": 2}}
    found, _ = run(snap, "SEC-CTL-001")
    assert len(found) == 2 and any("staging.example.com" in f.msg_de for f in found)


def test_the_check_is_quiet_for_clean_logs():
    snap = snap_of()
    snap.extra["ct"] = {"enabled": True, "skip": None, "hosts": ["www.example.com", "shop.example.com"],
                        "recent_issuers": {"A": 3}}
    assert run(snap, "SEC-CTL-001")[0] == []


def test_the_services_page_asks_before_it_switches_crtsh_on(qapp, env, monkeypatch):
    from claudios.ui import page_services

    old = get_lang()
    try:
        set_lang("de")
        page = page_services.create(None)
        page.retranslate()
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: False)
        page.ct.setChecked(True)
        assert page.ct.isChecked() is False and services.enabled("crtsh") is False
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: True)
        page.ct.setChecked(True)
        assert services.enabled("crtsh") is True
    finally:
        set_lang(old)


def test_the_texts_exist_in_both_languages_with_equal_placeholders():
    for key in ("svc.ct.switch", "svc.ct.info", "svc.ct.ask", "probe.crtsh"):
        assert TEXTS["de"][key] and TEXTS["en"][key]
