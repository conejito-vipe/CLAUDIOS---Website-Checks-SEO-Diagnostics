import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from claudios import paths
from claudios.checks import tools_html
from claudios.core.assetprobe import collect_assets
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult, ensure_in_tools, run_tool


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def make_snap(htmls, **extra):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    for index, html in enumerate(htmls):
        url = "https://example.com/" + (f"p{index}" if index else "")
        snap.pages.append(Page(url=url, depth=1, status=200, html=html, content_type="text/html"))
    snap.extra.update(extra)
    snap.status = "complete"
    return snap


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def patch_tools(monkeypatch, run):
    monkeypatch.setattr(tools_html, "tool_path", lambda name: Path("/tools") / name / "tool")
    monkeypatch.setattr(tools_html, "run_tool", run)


VNU = json.dumps({"messages": [
    {"type": "error", "message": "Bad thing", "lastLine": 3, "url": "file:/tmp/x/p0.html"},
    {"type": "error", "message": "Other", "lastLine": 5, "url": "file:/tmp/x/p0.html"},
    {"type": "info", "subType": "warning", "message": "Meh", "lastLine": 1, "url": "file:/tmp/x/p1.html"}]})


def test_vnu_results_are_mapped_to_pages(env, monkeypatch):
    calls = []

    def fake_run(args, *, cwd, timeout=None, root=None):
        calls.append([str(a) for a in args])
        return ToolResult(1, VNU, "", False)

    patch_tools(monkeypatch, fake_run)
    found, executed = run_checks(make_snap(["<html></html>", "<html></html>"]), 1, "standard",
                                 components=lambda name: True)
    val = [f for f in found if f.check_id == "HTM-VAL-001"]
    assert {(f.severity, f.url) for f in val} == {(S.ERROR, "https://example.com/"), (S.NOTE, "https://example.com/p1")}
    assert "Line 3: Bad thing (2 error(s) on this page)" in {f.evidence for f in val}
    assert executed["HTM-VAL-001"] == "ran"
    args = calls[0]
    assert "--stdout" in args and "p0.html" in args and "p1.html" in args
    assert not any(a.startswith("https:") for a in args)  # Werkzeuge bekommen nie eine Adresse


def test_unreadable_output_failure_and_missing_tool_are_never_passed(env, monkeypatch):
    patch_tools(monkeypatch, lambda args, **kw: ToolResult(0, "this is not json", "", False))
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard", components=lambda name: True)
    assert executed["HTM-VAL-001"] == "skipped:tool_output_unreadable"

    def failing(args, **kw):
        raise ClaudiosError(E.TOOL_FAILED, reason="timeout")

    patch_tools(monkeypatch, failing)
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard", components=lambda name: True)
    assert executed["HTM-VAL-001"] == "skipped:tool_failed"
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard", components=lambda name: False)
    assert executed["HTM-VAL-001"] == "skipped:component_missing:java,vnu"


def test_css_validator_results_and_missing_asset_data(env, monkeypatch):
    out = json.dumps({"cssvalidation": {"errors": [{"line": 1, "message": "bad"}],
                                        "warnings": [{"line": 2, "message": "w"}]}})
    patch_tools(monkeypatch, lambda args, **kw: ToolResult(0, out, "", False))
    assets = {"css": [{"url": "https://example.com/a.css", "status": 200, "error": None, "text": "a{color:red}"},
                      {"url": "https://example.com/b.css", "status": 404, "error": None, "text": ""}], "js": []}
    found, executed = run_checks(make_snap(["<html></html>"], assets=assets), 1, "standard",
                                 components=lambda name: True)
    css = [f for f in found if f.check_id == "CSS-VAL-001"]
    assert {f.severity for f in css} == {S.ERROR, S.NOTE} and executed["CSS-VAL-001"] == "ran"
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard", components=lambda name: True)
    assert executed["CSS-VAL-001"] == "skipped:no_asset_data"


def test_tool_runner_runs_in_tools_folder_only_with_limits(tmp_path):
    exe = Path(sys.executable)
    root = exe.parent.parent
    result = run_tool([exe, "-c", "print('hi')"], cwd=tmp_path, root=root)
    assert result.stdout.strip() == "hi" and result.returncode == 0
    with pytest.raises(ClaudiosError) as e:
        run_tool([exe, "-c", "import time; time.sleep(5)"], cwd=tmp_path, timeout=0.5, root=root)
    assert e.value.code == E.TOOL_FAILED
    with pytest.raises(ClaudiosError):
        ensure_in_tools(tmp_path / "evil.exe", root)
    with pytest.raises(ClaudiosError):
        ensure_in_tools(root / "x" / ".." / ".." / "evil.exe", root)


class FakeGK:
    cancel = None

    def __init__(self):
        self.calls = []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        path = urlsplit(url).path
        self.calls.append(path)
        status = 404 if path == "/gone.js" else 200
        return Response(url, status, {"content-type": "text/plain"}, [], f"body of {path}".encode(), False, 1)


ASSET_PAGE = ('<html><head><link rel="stylesheet" href="/a.css"><script src="/app.js"></script>'
              '<script src="/gone.js"></script><script src="https://cdn.other.test/x.js"></script></head></html>')


async def test_asset_probe_fetches_only_own_files():
    snap = make_snap([ASSET_PAGE])
    gk = FakeGK()
    data = await collect_assets(gk, snap)
    assert gk.calls == ["/a.css", "/app.js", "/gone.js"]
    assert data["css"][0]["text"] == "body of /a.css"
    assert [a["status"] for a in data["js"]] == [200, 404] and data["js"][1]["text"] == ""
    assert data["js_total"] == 2


CODE_PAGE = ('<html><head><script src="https://cdn.other.test/lib.js"></script>'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">'
             '<script src="https://cdn.other.test/ok.js" integrity="sha384-abc" crossorigin="anonymous"></script>'
             '</head><body><button onclick="x()">go</button><a href="javascript:void(0)">x</a></body></html>')
ASSETS = {
    "css": [{"url": "https://example.com/a.css", "status": 200, "error": None,
             "text": "@import url(b.css); a{color:red !important}\n/*# sourceMappingURL=a.css.map */"}],
    "js": [{"url": "https://example.com/app.js", "status": 200, "error": None,
            "text": 'eval(x); el.innerHTML = y; var k = "AKIAABCDEFGHIJKLMNOP";\n//# sourceMappingURL=app.js.map'}],
}


def test_code_quality_checks_find_the_planted_problems():
    found, executed = run_checks(make_snap([CODE_PAGE], assets=ASSETS), 1, "standard")
    got = pairs(found)
    for expected in (("JSS-PAT-001", S.WARNING), ("JSS-PAT-001", S.NOTE), ("JSS-SRI-001", S.WARNING),
                     ("JSS-MAP-001", S.NOTE), ("CSS-IMP-001", S.NOTE), ("HTM-INL-001", S.NOTE),
                     ("SEC-SEC-002", S.ERROR)):
        assert expected in got
    sri = [f for f in found if f.check_id == "JSS-SRI-001"]
    assert len(sri) == 1 and "cdn.other.test" in sri[0].msg_en  # Google Fonts und integrity sind ausgenommen
    assert all("AKIAABCDEFGHIJKLMNOP" not in f.evidence for f in found)
    assert executed["JSS-PAT-001"] == "ran" and executed["JSS-SRI-001"] == "ran"


def test_asset_based_checks_are_skipped_without_asset_data():
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard")
    for cid in ("JSS-PAT-001", "JSS-MAP-001", "CSS-IMP-001", "SEC-SEC-002"):
        assert executed[cid] == "skipped:no_asset_data"
    assert executed["JSS-SRI-001"] == "ran" and executed["HTM-INL-001"] == "ran"


def test_tls_certificate_check():
    def run(days, version="TLSv1.3", **more):
        data = {"version": version, "cipher": "X", "days_left": days, "issuer": "CA", "error": None, **more}
        found, executed = run_checks(make_snap(["<html></html>"], tls=data), 1, "standard")
        return [f for f in found if f.check_id == "TLS-CRT-001"], executed["TLS-CRT-001"]

    assert pairs(run(10)[0]) == {("TLS-CRT-001", S.ERROR)}
    assert pairs(run(25)[0]) == {("TLS-CRT-001", S.WARNING)}
    assert run(90) == ([], "ran")
    assert pairs(run(90, "TLSv1.2")[0]) == {("TLS-CRT-001", S.INFO)}
    assert run(0, error="OSError")[1] == "skipped:tls_probe_failed"
    _, executed = run_checks(make_snap(["<html></html>"]), 1, "standard")
    assert executed["TLS-CRT-001"] == "skipped:no_tls_data"


def test_new_tool_texts_exist_in_both_languages():
    from claudios.i18n.strings import TEXTS

    for lang in ("de", "en"):
        assert TEXTS[lang]["probe.assets"] and TEXTS[lang]["probe.tls"]
    assert set(TEXTS["de"]) == set(TEXTS["en"]) and paths.assets_dir is not None