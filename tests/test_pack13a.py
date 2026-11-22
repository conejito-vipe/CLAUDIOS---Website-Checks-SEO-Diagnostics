"""Paket 13: externe Links (Zeitlimit, träge Hosts, Fortschritt, Abbruch, keine Weiterleitungen), Abbruch der Prüfphase,
Verlauf standardmäßig an, Einstellungen."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from claudios import settings
from claudios.core import linkprobe
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.report import history


class FakeGk:
    def __init__(self, slow=(), status=200):
        self.cancel = None
        self.calls = []
        self.slow = set(slow)
        self.status = status

    async def fetch(self, url, *, method="GET", external=False, max_bytes=None, follow=True):
        self.calls.append((url, method, follow))
        if url.split("/")[2] in self.slow:
            await asyncio.sleep(5)
        return SimpleNamespace(status=self.status, downgrade=False, chain=[])


def _snap(links):
    return SimpleNamespace(pages=[SimpleNamespace(url="https://a.test/", external_links=links)])


async def test_a_dead_host_costs_at_most_two_timeouts(monkeypatch):
    monkeypatch.setattr(linkprobe, "LINK_TIMEOUT", 0.05)
    gk = FakeGk(slow={"dead.test"})
    links = [f"https://dead.test/{i}" for i in range(5)] + ["https://ok.test/"]
    result = await linkprobe.check_external_links(gk, _snap(links))
    dead = [r for r in result["results"] if "dead.test" in r["url"]]
    assert len(dead) == 5 and all(r["error"] == E.NET_TIMEOUT.value for r in dead)
    assert sum(1 for url, _method, _follow in gk.calls if "dead.test" in url) == 2
    ok = next(r for r in result["results"] if "ok.test" in r["url"])
    assert ok["status"] == 200 and ok["error"] is None and result["checked"] == 6


async def test_redirects_are_not_followed_only_reported():
    gk = FakeGk(status=301)
    result = await linkprobe.check_external_links(gk, _snap(["https://x.test/old"]))
    assert all(follow is False for _url, _method, follow in gk.calls)
    assert result["results"][0]["status"] == 301 and result["results"][0]["redirects"] == 1


async def test_progress_counts_up_with_the_address():
    seen = []
    links = [f"https://x{i}.test/" for i in range(3)]
    await linkprobe.check_external_links(FakeGk(), _snap(links), lambda url, cur, total: seen.append((url, cur, total)))
    assert seen == [(links[0], 1, 3), (links[1], 2, 3), (links[2], 3, 3)]


async def test_cancel_stops_the_link_check():
    gk = FakeGk()
    gk.cancel = asyncio.Event()
    gk.cancel.set()
    with pytest.raises(ClaudiosError) as error:
        await linkprobe.check_external_links(gk, _snap(["https://x.test/"]))
    assert error.value.code == E.SCAN_CANCELLED and gk.calls == []


def test_a_stop_request_skips_all_remaining_checks_and_marks_the_scan_aborted():
    snap = SimpleNamespace(abort=None, pages=[], status="complete")
    _findings, executed = run_checks(snap, 1, "standard", lambda name: True, should_stop=lambda: True)
    assert executed and snap.status == "aborted" and snap.abort is not None
    assert {state for cid, state in executed.items() if cid != "SYS-ABT-001"} == {"skipped:cancelled"}


def test_the_check_phase_reports_its_progress():
    snap = SimpleNamespace(abort=None, pages=[], status="complete")
    seen = []
    run_checks(snap, 1, "quick", lambda name: False, progress=lambda stage, cur, total: seen.append((stage, cur, total)))
    assert seen and seen[0][0].startswith("check:") and seen[-1][1] == seen[-1][2]


def test_the_history_is_on_by_default_and_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert history.enabled() is True
    history.set_enabled(False)
    assert history.enabled() is False
    history.set_enabled(True)
    assert history.enabled() is True


def test_settings_keep_the_off_switches(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert settings.load() == {"language": None, "allow_localhost": False}
    settings.save({"language": "de", "allow_localhost": False, "update_check": False})
    assert settings.load()["update_check"] is False
    settings.save({"language": "de", "allow_localhost": False, "update_check": True})
    assert "update_check" not in settings.load()
    path = settings._file()
    assert json.loads(path.read_text("utf-8")) == {"language": "de", "allow_localhost": False}
