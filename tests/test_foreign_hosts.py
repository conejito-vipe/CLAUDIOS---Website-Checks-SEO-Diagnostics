import copy
import dataclasses
import time
from types import SimpleNamespace

import pytest

from claudios.checks import load_all
from claudios.checks._util import CheckSkipped
from claudios.core import foreign, probe_zap
from claudios.core.limits import LIMITS
from claudios.core.registry import REGISTRY

TABLE = {"evil.test": {"A": ["10.0.0.5"]}, "cdn.test": {"A": ["8.8.8.8"]},
         "v6.test": {"AAAA": ["2001:4860:4860::8888"]}, "nat.test": {"AAAA": ["64:ff9b::a00:1"]}}


def look(host, rtype):
    return TABLE.get(host, {}).get(rtype, [])


def test_only_hosts_with_a_non_public_address_are_flagged():
    result = foreign.screen(["cdn.test", "evil.test", "v6.test", "nat.test", "gone.test"], look)
    assert result.private == ("evil.test", "nat.test")  # gone.test ohne Antwort: unbekannt, nicht verdächtig
    assert result.unchecked == 0


def test_ip_literals_are_judged_directly_and_the_target_is_skipped():
    assert foreign.screen(["10.0.0.1", "8.8.8.8", "[::1]"], look).private == ("10.0.0.1", "[::1]")
    assert foreign.screen(["evil.test"], look, skip=["EVIL.test."]).private == ()


def test_too_many_hosts_are_counted_as_unchecked(monkeypatch):
    monkeypatch.setattr(foreign, "LIMITS", dataclasses.replace(LIMITS, foreign_hosts_max=3))
    result = foreign.screen([f"h{i}.test" for i in range(10)], look)
    assert result.private == () and result.unchecked == 7


def test_the_time_budget_is_enforced(monkeypatch):
    monkeypatch.setattr(foreign, "LIMITS", dataclasses.replace(LIMITS, foreign_budget_seconds=0.1, foreign_workers=2))

    def slow(host, rtype):
        time.sleep(0.5)
        return []

    started = time.monotonic()
    result = foreign.screen(["a.test", "b.test", "c.test"], slow)
    assert result.unchecked == 3
    assert time.monotonic() - started < 0.4  # wartet nicht auf die laufenden Abfragen


def _page():
    return {"url": "https://example.com/", "third_party": {"evil.test": 2, "cdn.test": 1},
            "failed": [{"url": "https://evil.test/a.js", "reason": "x"}, {"url": "https://cdn.test/b.js", "reason": "x"}],
            "bad_status": [{"url": "https://evil.test/c", "status": 404}],
            "cookies": [{"name": "a", "domain": ".evil.test"}, {"name": "b", "domain": "example.com"}]}


def test_browser_data_of_a_flagged_host_is_discarded():
    data = {"browser": "", "error": None, "pages": [_page()]}
    foreign.screen_browser(data, look)
    page = data["pages"][0]
    assert page["third_party"] == {"cdn.test": 1}
    assert [f["url"] for f in page["failed"]] == ["https://cdn.test/b.js"]
    assert page["bad_status"] == []
    assert [c["name"] for c in page["cookies"]] == ["b"]
    assert data["foreign_private"] == ["evil.test"] and "foreign_unchecked" not in data


def test_browser_data_stays_unchanged_when_all_hosts_are_fine():
    page = _page()
    page["third_party"] = {"cdn.test": 1, "gone.test": 1}
    data = {"browser": "", "error": None, "pages": [page]}
    before = copy.deepcopy(data)
    foreign.screen_browser(data, look)
    assert data == before


def test_zap_hosts_are_normalised(monkeypatch):
    monkeypatch.setattr(probe_zap, "_json", lambda client, path, **params: {
        "hosts": ["Example.com", "https://cdn.test:443", "evil.test:8443", 5]})
    assert probe_zap._seen_hosts(None) == {"example.com", "cdn.test", "evil.test"}


@pytest.mark.parametrize("error", [probe_zap._Skip("zap_api_failed"), RuntimeError("boom")])
def test_a_failing_host_list_means_unknown_and_never_aborts(monkeypatch, error):
    def broken(client, path, **params):
        raise error

    monkeypatch.setattr(probe_zap, "_json", broken)
    assert probe_zap._seen_hosts(None) == set()


def test_zap_alerts_of_a_flagged_host_are_dropped():
    result = {"skip": None, "alerts": [{"url": "https://example.com/"}, {"url": "https://evil.test/x"}]}
    out = probe_zap._screen(result, {"example.com", "evil.test", "cdn.test"}, "example.com", look)
    assert out["alerts"] == [{"url": "https://example.com/"}]
    assert out["foreign_private"] == ["evil.test"] and "foreign_unchecked" not in out


def _check(extra):
    load_all()
    snap = SimpleNamespace(target=SimpleNamespace(url="https://example.com/"), extra=extra)
    return REGISTRY["BRW-FRN-001"].fn(snap)


def test_the_check_reports_flagged_hosts_from_browser_and_zap():
    out = _check({"browser": {"browser": "", "error": None, "pages": [], "foreign_private": ["evil.test"]},
                  "zap": {"skip": None, "alerts": [], "foreign_private": ["evil.test", "nat.test"],
                          "foreign_unchecked": 2}})
    assert len(out) == 3  # zwei Hosts (evil.test nur einmal) und ein Hinweis auf nicht geprüfte Hosts
    assert "evil.test" in repr(out[0]) and "nat.test" in repr(out[1])


def test_the_check_is_quiet_without_findings_and_skipped_without_data():
    assert _check({"browser": {"browser": "", "error": None, "pages": []}}) == []
    with pytest.raises(CheckSkipped) as skipped:
        _check({"browser": {"error_reason": "tool_not_found", "pages": []}})
    assert skipped.value.reason == "no_browser_data"
