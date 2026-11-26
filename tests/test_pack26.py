"""Paket 26: HTM-VAL-001 fasst Seiten mit gleichem Ergebnis in einer Zeile zusammen (Zahl je Seite im Beleg)."""
from __future__ import annotations

import json
from pathlib import Path

from claudios.checks import tools_html
from claudios.checks._util import S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult
from claudios.report.report import group_findings
from claudios.ui.finding_detail import meta_for, meta_text


def make_snap(count):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    for i in range(count):
        snap.pages.append(Page(url=f"https://example.com/p{i}", depth=1, status=200, html="<html></html>",
                               content_type="text/html"))
    return snap


def setup(monkeypatch, tmp_path, build):
    """build(Nummer der Seite) -> Liste der vnu-Meldungen (ohne url)."""
    def fake_run(args, *, cwd, **kw):
        files = [str(a) for a in args if str(a).endswith(".html")]
        msgs = []
        for name in files:
            for message in build(int(name[1:-5])):
                msgs.append({**message, "url": "file:///tmp/" + name})
        return ToolResult(0, json.dumps({"messages": msgs}), "", False)

    monkeypatch.setattr(tools_html, "_tools", lambda *names: [Path("java"), Path("vnu.jar")])
    monkeypatch.setattr(tools_html, "run_tool", fake_run)
    monkeypatch.setattr(tools_html.paths, "cache_dir", lambda: tmp_path)


def run(snap):
    func = getattr(tools_html.html_validation, "__wrapped__", tools_html.html_validation)
    return func(snap)


def errors(count):
    return [{"type": "error", "lastLine": 7, "message": "boom"}] * count


def test_pages_with_errors_become_one_group_with_the_page_count(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, lambda i: errors(i + 1))
    found = run(make_snap(3))
    assert len(found) == 3 and {f.msg_de for f in found} == {"Seiten mit HTML-Fehlern laut W3C Nu Html Checker"}
    assert not any(ch.isdigit() for f in found for ch in (f.msg_de + f.msg_en).replace("W3C", ""))
    assert all(f.severity == S.ERROR for f in found)
    groups = group_findings(found)
    assert len(groups) == 1 and groups[0]["count"] == 3


def test_the_evidence_keeps_the_line_and_the_number_of_messages_of_the_page(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, lambda i: errors(i + 1))
    found = run(make_snap(3))
    assert found[0].evidence.startswith("Line 7: boom")
    assert "(1 error(s) on this page)" in found[0].evidence
    assert "(3 error(s) on this page)" in found[2].evidence


def test_warnings_only_are_a_note_and_a_separate_group(monkeypatch, tmp_path):
    warning = {"type": "info", "subType": "warning", "lastLine": 2, "message": "hmm"}
    setup(monkeypatch, tmp_path, lambda i: errors(1) + [warning] if i == 0 else [warning])
    found = run(make_snap(2))
    assert sorted(int(f.severity) for f in found) == sorted([int(S.ERROR), int(S.NOTE), int(S.NOTE)])
    groups = group_findings(found)
    assert len(groups) == 2 and sorted(g["count"] for g in groups) == [1, 2]
    assert any("HTML-Warnungen" in g["msg_de"] for g in groups)


def test_pages_without_messages_give_no_finding(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, lambda i: [])
    assert run(make_snap(2)) == []


def test_the_rating_text_explains_the_summary():
    logic = meta_text(meta_for("HTM-VAL-001"), "logic", "de")
    assert "mindestens einen Fehler" in logic and "Anzahl" in logic and "98 HTML-Fehler" not in logic
    assert "at least one error" in meta_text(meta_for("HTM-VAL-001"), "logic", "en")
