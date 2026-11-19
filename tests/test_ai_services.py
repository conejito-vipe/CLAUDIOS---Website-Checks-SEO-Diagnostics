import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest

from claudios.core import probe_ai, probe_rdap, services
from claudios.core.engine import run_checks
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot
from claudios.i18n.strings import TEXTS, get_lang, set_lang


def page(html="<html></html>", url="https://example.com/"):
    return Page(url=url, depth=1, status=200, html=html, content_type="text/html; charset=utf-8")


def snap_of(robots=None):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(page())
    snap.robots_txt = robots
    snap.status = "complete"
    return snap


def run(snap, cid):
    found, executed = run_checks(snap, 1, "standard")
    return [f for f in found if f.check_id == cid], executed[cid]


def sevs(found):
    return sorted(f.severity for f in found)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


ROBOTS = ("User-agent: GPTBot\nDisallow: /\n\nUser-agent: CCBot\nDisallow: /private/\n\n"
          "User-agent: ClaudeBot\nAllow: /\n\nUser-agent: *\nDisallow:\n")


def test_ai_crawler_rules_are_sorted_into_blocked_partial_and_allowed():
    found, state = run(snap_of(ROBOTS), "SEO-AIC-001")
    assert state == "ran" and {f.severity for f in found} == {S.INFO}
    assert [f.evidence for f in found] == ["GPTBot", "CCBot", "ClaudeBot"]


def test_a_rule_for_everybody_blocks_the_unnamed_ai_crawlers_too():
    found, _ = run(snap_of("User-agent: *\nDisallow: /\n"), "SEO-AIC-001")
    assert len(found) == 1 and "*" in found[0].msg_en
    found, _ = run(snap_of("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /\n"), "SEO-AIC-001")
    assert len(found) == 2


def test_no_ai_rules_is_reported_once_and_a_missing_robots_file_is_skipped():
    found, _ = run(snap_of("User-agent: *\nDisallow: /admin/\n"), "SEO-AIC-001")
    assert len(found) == 1 and "no rules" in found[0].msg_en
    assert run(snap_of(None), "SEO-AIC-001") == ([], "skipped:no_robots_txt")


def ai_snap(**rec):
    snap = snap_of()
    snap.extra["ai"] = {"llms": {"path": "/llms.txt", "status": 200, "error": None, "content_type": "text/plain",
                                 "text": "", "truncated": False, **rec}}
    return snap


GOOD_LLMS = "# My Site\n\n> Short summary.\n\n## Docs\n\n- [Guide](https://example.com/guide): intro\n"


def test_llms_txt():
    assert run(ai_snap(text=GOOD_LLMS), "SEO-LLM-001") == ([], "ran")
    assert sevs(run(ai_snap(status=404), "SEO-LLM-001")[0]) == [S.INFO]
    assert sevs(run(ai_snap(text="<html>", content_type="text/html"), "SEO-LLM-001")[0]) == [S.NOTE]
    assert sevs(run(ai_snap(text="Intro\n"), "SEO-LLM-001")[0]) == [S.NOTE, S.NOTE]
    assert sevs(run(ai_snap(text="  \n"), "SEO-LLM-001")[0]) == [S.NOTE]
    insecure = "# T\n\n## D\n- [a](" + "http" + "://example.com/a)\n"
    assert sevs(run(ai_snap(text=insecure), "SEO-LLM-001")[0]) == [S.NOTE]
    assert sevs(run(ai_snap(text=GOOD_LLMS, truncated=True), "SEO-LLM-001")[0]) == [S.INFO]
    assert run(ai_snap(status=None, error="CLA-NET-001"), "SEO-LLM-001")[1] == "skipped:llms_unreachable"


def rdap_snap(days=None, statuses=(), **extra):
    snap = snap_of()
    expires = (datetime.now(UTC) + timedelta(days=days)).isoformat() if days is not None else None
    snap.extra["rdap"] = {"enabled": True, "skip": None, "expires": expires, "statuses": list(statuses), **extra}
    return snap


def test_domain_expiry_thresholds_and_statuses():
    assert sevs(run(rdap_snap(10), "SEC-DOM-001")[0]) == [S.ERROR]
    assert sevs(run(rdap_snap(20), "SEC-DOM-001")[0]) == [S.WARNING]
    assert sevs(run(rdap_snap(45), "SEC-DOM-001")[0]) == [S.NOTE]
    assert run(rdap_snap(200), "SEC-DOM-001") == ([], "ran")
    assert sevs(run(rdap_snap(-3), "SEC-DOM-001")[0]) == [S.ERROR]
    assert sevs(run(rdap_snap(None), "SEC-DOM-001")[0]) == [S.INFO]
    assert sevs(run(rdap_snap(200, ["client hold"]), "SEC-DOM-001")[0]) == [S.WARNING]
    assert sevs(run(rdap_snap(200, ["pending delete"]), "SEC-DOM-001")[0]) == [S.ERROR]
    assert run(rdap_snap(200, ["client transfer prohibited"]), "SEC-DOM-001") == ([], "ran")


def test_checks_without_probe_data_are_skipped_and_never_passed():
    plain = snap_of()
    _, executed = run_checks(plain, 1, "standard")
    assert executed["SEO-LLM-001"] == "skipped:no_ai_data"
    assert executed["SEC-DOM-001"] == "skipped:no_rdap_data"
    off = snap_of()
    off.extra["rdap"] = {"enabled": False, "skip": "rdap_disabled"}
    assert run(off, "SEC-DOM-001")[1] == "skipped:rdap_disabled"


class FakeGK:
    cancel = None

    def __init__(self, responses):
        self.responses, self.calls = responses, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        assert method == "GET"
        parts = urlsplit(url)
        self.calls.append((parts.netloc, parts.path, external))
        status, ctype, body = self.responses.get((parts.netloc, parts.path), (404, "text/html", b""))
        return Response(url, status, {"content-type": ctype}, [], body, False, 1)


async def test_the_ai_probe_makes_exactly_one_request_to_the_site():
    gk = FakeGK({("example.com", "/llms.txt"): (200, "text/plain", GOOD_LLMS.encode())})
    data = await probe_ai.collect(gk, snap_of(), None)
    assert data["llms"]["status"] == 200 and data["llms"]["text"] == GOOD_LLMS
    assert gk.calls == [("example.com", "/llms.txt", False)] and probe_ai.MIN_LEVEL == 1


BOOTSTRAP = json.dumps({"services": [[["com"], ["https://rdap.registry.test/com/v1"]]]}).encode()
DOMAIN = json.dumps({"events": [{"eventAction": "registration", "eventDate": "2001-01-01T00:00:00Z"},
                                {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"}],
                     "status": ["Client Transfer Prohibited"]}).encode()
RESPONSES = {("data.iana.org", "/rdap/dns.json"): (200, "application/json", BOOTSTRAP),
             ("rdap.registry.test", "/com/v1/domain/example.com"): (200, "application/rdap+json", DOMAIN)}


async def test_the_rdap_probe_does_nothing_while_the_switch_is_off(env):
    gk = FakeGK(RESPONSES)
    assert await probe_rdap.collect(gk, snap_of(), None) == {"enabled": False, "skip": "rdap_disabled"}
    assert gk.calls == []


async def test_the_rdap_probe_asks_iana_and_then_the_registry_through_the_gatekeeper(env):
    services.set_enabled("rdap", True)
    gk = FakeGK(RESPONSES)
    data = await probe_rdap.collect(gk, snap_of(), None)
    assert data["skip"] is None and data["expires"].startswith("2030-01-01")
    assert data["statuses"] == ["client transfer prohibited"]
    assert gk.calls == [("data.iana.org", "/rdap/dns.json", True),
                        ("rdap.registry.test", "/com/v1/domain/example.com", True)]


async def test_rdap_failures_become_a_reason_and_never_a_result(env):
    services.set_enabled("rdap", True)
    down = FakeGK({("data.iana.org", "/rdap/dns.json"): (500, "text/html", b"")})
    assert (await probe_rdap.collect(down, snap_of(), None))["skip"] == "rdap_http_500"
    other = json.dumps({"services": [[["org"], ["https://rdap.registry.test/org/"]]]}).encode()
    no_server = FakeGK({("data.iana.org", "/rdap/dns.json"): (200, "application/json", other)})
    assert (await probe_rdap.collect(no_server, snap_of(), None))["skip"] == "rdap_no_server"
    junk = FakeGK({**RESPONSES, ("rdap.registry.test", "/com/v1/domain/example.com"): (200, "text/plain", b"[")})
    assert (await probe_rdap.collect(junk, snap_of(), None))["skip"] == "rdap_unreadable"


def test_the_switch_is_off_by_default_persists_and_knows_only_its_services(env):
    assert services.enabled("rdap") is False
    services.set_enabled("rdap", True)
    assert services.enabled("rdap") is True
    services.set_enabled("rdap", False)
    assert services.enabled("rdap") is False
    with pytest.raises(ValueError):
        services.set_enabled("other", True)
    assert services.enabled("other") is False


def test_texts_exist_in_both_languages():
    keys = [k for k in TEXTS["de"] if k.startswith("svc.")] + ["nav.services", "probe.ai", "probe.rdap"]
    assert len(keys) >= 10
    for key in keys:
        assert TEXTS["de"][key].strip() and TEXTS["en"][key].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_services_page_asks_before_it_switches_rdap_on(qapp, env, monkeypatch):
    from claudios.ui import page_services

    old = get_lang()
    try:
        set_lang("de")
        page = page_services.create(None)
        page.retranslate()
        assert page.rdap.isChecked() is False and "ausgeschaltet" in page.state.text()
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: False)
        page.rdap.setChecked(True)
        assert page.rdap.isChecked() is False and services.enabled("rdap") is False
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: True)
        page.rdap.setChecked(True)
        assert services.enabled("rdap") is True and "eingeschaltet" in page.state.text()
        page.rdap.setChecked(False)
        assert services.enabled("rdap") is False
    finally:
        set_lang(old)
