"""HTML-Validierung (vnu) in Gruppen: Seitenzahl begrenzt, mehrere Läufe, abgeschnittene Ausgabe wird nicht als bestanden gewertet."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudios.checks import tools_html
from claudios.checks._util import CheckSkipped
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult


def make_snap(count):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    for i in range(count):
        snap.pages.append(Page(url=f"https://example.com/p{i}", depth=1, status=200, html="<html></html>",
                               content_type="text/html"))
    return snap


def fake_env(monkeypatch, tmp_path, *, truncated=False, text=None):
    calls = []

    def fake_run(args, *, cwd, **kw):
        files = [str(a) for a in args if str(a).endswith(".html")]
        calls.append(files)
        msgs = [{"type": "error", "url": "file:///tmp/" + f, "lastLine": 3, "message": "boom"} for f in files]
        return ToolResult(0, text if text is not None else json.dumps({"messages": msgs}), "", truncated)

    monkeypatch.setattr(tools_html, "_tools", lambda *names: [Path("java"), Path("vnu.jar")])
    monkeypatch.setattr(tools_html, "run_tool", fake_run)
    monkeypatch.setattr(tools_html.paths, "cache_dir", lambda: tmp_path)
    return calls


def run(snap):
    func = getattr(tools_html.html_validation, "__wrapped__", tools_html.html_validation)
    return func(snap)


def test_pages_are_limited_and_checked_in_groups(monkeypatch, tmp_path):
    calls = fake_env(monkeypatch, tmp_path)
    found = run(make_snap(40))
    assert [len(c) for c in calls] == [10, 10, 5]
    assert len(found) == 25 and all(f.check_id == "HTM-VAL-001" for f in found)
    assert len({name for c in calls for name in c}) == 25


def test_truncated_output_is_not_executed(monkeypatch, tmp_path):
    fake_env(monkeypatch, tmp_path, truncated=True, text='{"messages": [')
    with pytest.raises(CheckSkipped) as info:
        run(make_snap(3))
    assert info.value.reason == "tool_output_unreadable"


def test_unreadable_output_is_logged_with_size(monkeypatch, tmp_path, caplog):
    fake_env(monkeypatch, tmp_path, text="not json")
    caplog.set_level("INFO", logger="claudios")
    with pytest.raises(CheckSkipped):
        run(make_snap(2))
    assert "vnu output is not JSON: 8 bytes for 2 files" in caplog.text
