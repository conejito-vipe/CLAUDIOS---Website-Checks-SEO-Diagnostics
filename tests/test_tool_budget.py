import dataclasses
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import pytest

from claudios.core import engine, toolbudget, toolrunner
from claudios.core.audit_log import AuditLog
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.limits import LIMITS
from claudios.core.toolbudget import ScanBudget, acquire, classify, release, scan_budget


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make(clock):
    return ScanBudget(clock=clock, sleep=clock.sleep)


def use(budget, clock, kind, seconds):
    slot = budget.begin(kind)
    clock.now += seconds
    budget.end(slot)
    return slot


def limits(monkeypatch, **changes):
    monkeypatch.setattr(toolbudget, "LIMITS", dataclasses.replace(LIMITS, **changes))


@pytest.mark.parametrize("args,kind", [
    (["node", "C:\\tools\\browser_probe.js", "in.json", "out.json"], "browser"),
    (["node", "/work/zap_probe.js", "in.json", "out.json"], "zap"),
    (["python.exe", "-m", "sslyze", "--tlsv1_2", "example.com:443{8.8.8.8}"], "sslyze"),
    (["python.exe", "-m", "pip", "install", "--no-binary=sslyze"], None),
    (["node", "eslint.js", "a.js"], None),
    (["java", "-jar", "vnu.jar"], None)])
def test_only_browser_zap_and_sslyze_are_recognised(args, kind):
    assert classify(args) == kind


def test_the_callers_use_the_names_the_classification_relies_on():
    def source(module):
        return Path(find_spec(module).origin).read_text("utf-8")

    assert "browser_probe.js" in source("claudios.checks._browser")
    assert "zap_probe.js" in source("claudios.core.probe_zap")
    assert '"-m", "sslyze"' in source("claudios.checks.sslchecks")


def test_the_first_run_has_no_pause_and_the_next_one_waits():
    clock = Clock()
    budget = make(clock)
    first = use(budget, clock, "browser", 5)
    assert clock.slept == [] and first.max_seconds == LIMITS.tool_total_seconds
    clock.now += 4
    use(budget, clock, "sslyze", 1)
    assert clock.slept == [LIMITS.tool_min_pause_seconds - 4]


def test_the_total_time_shrinks_the_limit_and_finally_refuses(monkeypatch):
    limits(monkeypatch, tool_total_seconds=100.0, tool_min_run_seconds=30.0, tool_min_pause_seconds=0.0)
    clock = Clock()
    budget = make(clock)
    first = use(budget, clock, "browser", 40)
    assert first.max_seconds == 100.0
    second = budget.begin("zap")
    assert second.max_seconds == 60.0 and second.cap(120.0) == 60.0 and second.cap(10.0) == 10.0
    clock.now += 50
    budget.end(second)
    with pytest.raises(ClaudiosError) as error:
        budget.begin("sslyze")  # nur noch 10 Sekunden übrig
    assert error.value.code == E.TOOL_FAILED


def test_the_number_of_runs_per_kind_is_limited(monkeypatch):
    limits(monkeypatch, tool_runs_per_kind=1, tool_min_pause_seconds=0.0)
    clock = Clock()
    budget = make(clock)
    use(budget, clock, "browser", 1)
    with pytest.raises(ClaudiosError):
        budget.begin("browser")
    use(budget, clock, "zap", 1)


def test_nothing_happens_outside_a_scan():
    assert toolbudget.current() is None
    assert acquire(["node", "browser_probe.js"]) is None
    release(None)


def test_other_tools_are_not_counted_inside_a_scan():
    budget = make(Clock())
    with scan_budget(budget):
        assert acquire(["node", "eslint.js"]) is None
    assert budget.used == 0 and budget.runs == {}


def test_the_budget_is_only_active_inside_the_with_block():
    outer = ScanBudget()
    with scan_budget(outer) as active:
        assert active is outer and toolbudget.current() is outer
        with scan_budget() as inner:
            assert toolbudget.current() is inner
        assert toolbudget.current() is outer
    assert toolbudget.current() is None


def _fake_run(clock, timeouts, seconds=12.0):
    def run(command, **kwargs):
        timeouts.append(kwargs["timeout"])
        clock.now += seconds
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    return run


def test_run_tool_caps_the_timeout_and_counts_the_time(monkeypatch, tmp_path):
    limits(monkeypatch, tool_total_seconds=50.0, tool_min_run_seconds=10.0, tool_min_pause_seconds=0.0)
    clock, timeouts = Clock(), []
    monkeypatch.setattr(toolrunner, "ensure_in_tools", lambda *args, **kwargs: None)
    monkeypatch.setattr(toolrunner.subprocess, "run", _fake_run(clock, timeouts))
    budget = make(clock)
    with scan_budget(budget):
        toolrunner.run_tool(["node", "zap_probe.js"], cwd=tmp_path, timeout=120.0)
        toolrunner.run_tool(["node", "zap_probe.js"], cwd=tmp_path, timeout=120.0)
    assert timeouts == [50.0, 38.0] and budget.used == 24.0


def test_run_tool_refuses_without_budget_and_never_starts_the_program(monkeypatch, tmp_path):
    limits(monkeypatch, tool_total_seconds=20.0, tool_min_run_seconds=30.0)
    clock, timeouts = Clock(), []
    monkeypatch.setattr(toolrunner, "ensure_in_tools", lambda *args, **kwargs: None)
    monkeypatch.setattr(toolrunner.subprocess, "run", _fake_run(clock, timeouts))
    with scan_budget(make(clock)), pytest.raises(ClaudiosError) as error:
        toolrunner.run_tool(["python", "-m", "sslyze", "example.com:443"], cwd=tmp_path)
    assert error.value.code == E.TOOL_FAILED and timeouts == []


def test_run_tool_is_unchanged_outside_a_scan(monkeypatch, tmp_path):
    clock, timeouts = Clock(), []
    monkeypatch.setattr(toolrunner, "ensure_in_tools", lambda *args, **kwargs: None)
    monkeypatch.setattr(toolrunner.subprocess, "run", _fake_run(clock, timeouts))
    toolrunner.run_tool(["node", "zap_probe.js"], cwd=tmp_path, timeout=120.0)
    toolrunner.run_tool(["node", "x.js"], cwd=tmp_path)
    assert timeouts == [120.0, LIMITS.tool_timeout_seconds]


async def test_run_scan_opens_the_budget_only_while_it_runs(monkeypatch, tmp_path):
    seen = []

    async def fake_crawl(gk, snap, progress=None):
        seen.append(toolbudget.current())

    async def fake_probes(gk, snap, doh, progress):
        seen.append(toolbudget.current())

    monkeypatch.setattr(engine, "crawl", fake_crawl)
    monkeypatch.setattr(engine, "gather_probes", fake_probes)
    monkeypatch.setattr(engine, "run_checks", lambda snap, level, profile, components: ([], {}))
    monkeypatch.setattr(engine, "compute_scores", lambda findings, executed: {"overall": 0})
    result = await engine.run_scan("example.com", level=1, confirmed=True, audit=AuditLog(tmp_path / "audit.jsonl"),
                                   lock_path=tmp_path / "scan.lock")
    assert result.snapshot.status == "complete"
    assert len(seen) == 2 and all(isinstance(budget, ScanBudget) for budget in seen)
    assert toolbudget.current() is None
