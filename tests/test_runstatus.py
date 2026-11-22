"""Status "mit Einschränkungen": gewollte Gründe zählen nicht, echte Probleme schon."""
from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from claudios.core import engine as engine_module
from claudios.core.audit_log import AuditLog
from claudios.core.engine import run_scan
from claudios.core.net import Response
from claudios.core.runstatus import limits_scan


@pytest.mark.parametrize("state", ["ran", "skipped:level2_required", "skipped:no_gsc_data",
                                   "skipped:rdap_disabled", "skipped:safebrowsing_disabled", "skipped:psi_disabled"])
def test_intended_reasons_do_not_limit(state):
    assert limits_scan(state) is False


@pytest.mark.parametrize("state", ["skipped:component_missing:java,vnu", "skipped:tool_failed",
                                   "skipped:dns_unreachable", "skipped:cancelled", "skipped:scan_aborted",
                                   "skipped:no_link_data", "skipped:something_new", "failed", ""])
def test_real_problems_and_unknown_reasons_limit(state):
    assert limits_scan(state) is True


class FakeResolver:
    async def query(self, name, rtype):
        return []


class ScanGK:
    def __init__(self, target, *, resolver, allow_localhost=False, cancel=None):
        self.cancel, self.requests, self.bytes_total = cancel, 0, 0

    async def fetch(self, url, **kw):
        self.requests += 1
        if urlsplit(url).path == "/robots.txt":
            return Response(url, 404, {}, [], b"", False, 1)
        html = '<!doctype html><html lang="en"><head><title>t</title></head><body><a href="/">home</a></body></html>'
        return Response(url, 200, {"content-type": "text/html; charset=utf-8"}, [], html.encode(), False, 1)

    async def aclose(self):
        return None


async def status_for(tmp_path, monkeypatch, executed):
    monkeypatch.setattr(engine_module, "Gatekeeper", ScanGK)
    monkeypatch.setattr(engine_module, "run_checks", lambda *a, **k: ([], dict(executed)))
    monkeypatch.setattr(engine_module, "compute_scores", lambda *a, **k: {"overall": 0, "categories": {}})
    result = await run_scan("example.com", level=1, profile="quick", confirmed=True,
                            audit=AuditLog(tmp_path / "audit.jsonl"), lock_path=tmp_path / "scan.lock",
                            resolver=FakeResolver())
    return result.snapshot.status


async def test_scan_stays_complete_with_only_intended_skips(tmp_path, monkeypatch):
    executed = {"A-AAA-001": "ran", "B-BBB-001": "skipped:level2_required", "C-CCC-001": "skipped:psi_disabled",
                "D-DDD-001": "skipped:no_gsc_data"}
    assert await status_for(tmp_path, monkeypatch, executed) == "complete"


async def test_scan_is_limited_when_a_tool_is_missing(tmp_path, monkeypatch):
    executed = {"A-AAA-001": "ran", "B-BBB-001": "skipped:level2_required",
                "C-CCC-001": "skipped:component_missing:java,vnu"}
    assert await status_for(tmp_path, monkeypatch, executed) == "limited"
