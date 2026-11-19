import json
import shutil
from pathlib import Path

import pytest

from claudios import paths
from claudios.checks import _browser
from claudios.checks._util import CheckSkipped
from claudios.components import manager, playwrighttools
from claudios.components.extra_playwright import COMPONENT as PLAYWRIGHT
from claudios.components.lock import load_lock
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult

PREFIXES = ("BRW-", "PRV-BRW")
IDS = ("BRW-AXE-001", "BRW-CON-001", "BRW-PRF-001", "BRW-RSP-001", "PRV-BRW-001")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


@pytest.fixture
def with_script(env):
    script = paths.tools_dir() / "playwright" / "browser_probe.js"
    script.parent.mkdir(parents=True)
    script.write_text("//", "utf-8")
    return script


def make_snap(count=1, profile="standard", target="example.com", allow_localhost=False):
    snap = Snapshot(target=normalize_input(target, allow_localhost), level=1, profile=profile)
    for index in range(count):
        url = "https://example.com/" + (f"p{index}" if index else "")
        snap.pages.append(Page(url=url, depth=1, status=200, html="<html></html>", content_type="text/html"))
    snap.status = "complete"
    return snap


PAGE = {
    "url": "https://example.com/", "final_url": "https://example.com/", "status": 200, "error": None,
    "console": [{"type": "error", "text": "x is not defined"}, {"type": "warning", "text": "w"}],
    "page_errors": ["TypeError: boom"],
    "failed": [{"url": "https://example.com/a.png", "reason": "net::ERR_FAILED"}],
    "bad_status": [{"url": "https://example.com/missing.css", "status": 404}],
    "third_party": {"fonts.googleapis.com": 2, "www.googletagmanager.com": 1, "cdn.unknown.test": 1},
    "insecure_blocked": [],
    "cookies": [{"name": "_ga", "secure": True, "httpOnly": False, "sameSite": "Lax", "domain": ".example.com"},
                {"name": "sid", "secure": True, "httpOnly": True, "sameSite": "Lax", "domain": "example.com"}],
    "axe": [{"id": "image-alt", "impact": "critical", "help": "Images must have alternative text",
             "url": "https://dequeuniversity.com/rules/axe/4.10/image-alt", "nodes": 3},
            {"id": "region", "impact": "moderate", "help": "Content should be contained by landmarks",
             "url": "https://dequeuniversity.com/rules/axe/4.10/region", "nodes": 1}],
    "overflow": {"360": True, "768": False, "1280": False},
    "metrics": {"lcp": 4500, "cls": 0.3, "requests": 200, "bytes": 1000000},
}
CLEAN = {
    "url": "https://example.com/", "final_url": "https://example.com/", "status": 200, "error": None,
    "console": [], "page_errors": [], "failed": [], "bad_status": [], "third_party": {}, "insecure_blocked": [],
    "cookies": [{"name": "sid", "secure": True, "httpOnly": True, "sameSite": "Lax", "domain": "example.com"}],
    "axe": [], "overflow": {"360": False, "768": False, "1280": False},
    "metrics": {"lcp": 1200, "cls": 0.01, "requests": 20, "bytes": 100000},
}


class FakeBrowser:
    def __init__(self, pages=None, raw=None, fail=False, error=None):
        self.pages, self.raw, self.fail, self.error, self.calls = pages or [], raw, fail, error, []

    def __call__(self, args, *, cwd, timeout=None, root=None, extra_env=None):
        args = [str(a) for a in args]
        self.calls.append((args, json.loads(Path(args[2]).read_text("utf-8")), extra_env))
        if self.fail:
            raise ClaudiosError(E.TOOL_FAILED, reason="timeout")
        text = self.raw if self.raw is not None else json.dumps(
            {"browser": "1", "error": self.error, "pages": self.pages})
        Path(args[3]).write_text(text, "utf-8")
        return ToolResult(0, "", "", False)


def patch(monkeypatch, fake):
    monkeypatch.setattr(_browser, "tool_path", lambda name: paths.tools_dir() / "node" / "node.exe")
    monkeypatch.setattr(_browser, "_pin_ip", lambda snap: "93.184.216.34")
    monkeypatch.setattr(_browser, "run_tool", fake)


def run(fake, monkeypatch, snap=None, components=lambda name: True):
    patch(monkeypatch, fake)
    found, executed = run_checks(snap or make_snap(), 1, "standard", components=components)
    return [f for f in found if f.check_id.startswith(PREFIXES)], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def test_browser_results_are_mapped_by_all_five_checks_with_one_browser_run(with_script, monkeypatch):
    fake = FakeBrowser([PAGE])
    found, executed = run(fake, monkeypatch)
    got = pairs(found)
    for expected in (("BRW-CON-001", S.WARNING), ("BRW-CON-001", S.NOTE), ("BRW-AXE-001", S.ERROR),
                     ("BRW-AXE-001", S.NOTE), ("BRW-RSP-001", S.WARNING), ("BRW-PRF-001", S.WARNING),
                     ("BRW-PRF-001", S.NOTE), ("PRV-BRW-001", S.WARNING), ("PRV-BRW-001", S.NOTE),
                     ("PRV-BRW-001", S.INFO)):
        assert expected in got
    assert all(executed[cid] == "ran" for cid in IDS)
    assert len(fake.calls) == 1
    args, payload, env_ = fake.calls[0]
    assert payload["urls"] == ["https://example.com/"] and payload["host"] == "example.com"
    assert payload["registrable"] == "example.com" and payload["ip"] == "93.184.216.34" and payload["axe"] is True
    assert "PLAYWRIGHT_BROWSERS_PATH" in env_ and not any(a.startswith("https:") for a in args)
    rsp = [f for f in found if f.check_id == "BRW-RSP-001"]
    assert len(rsp) == 1 and "360px" in rsp[0].msg_en
    assert len([f for f in found if f.check_id == "PRV-BRW-001" and f.severity == S.WARNING]) == 2
    assert any("Google Fonts" in f.msg_en for f in found)


def test_clean_page_has_no_findings(with_script, monkeypatch):
    found, executed = run(FakeBrowser([CLEAN]), monkeypatch)
    assert found == [] and all(executed[cid] == "ran" for cid in IDS)


def test_pages_that_failed_to_load_are_reported_but_offsite_redirects_are_not(with_script, monkeypatch):
    broken = {**CLEAN, "error": "Timeout 30000ms exceeded"}
    offsite = {**CLEAN, "url": "https://example.com/p1", "error": "offsite_redirect"}
    found, _ = run(FakeBrowser([broken, offsite]), monkeypatch)
    assert pairs(found) == {("BRW-CON-001", S.WARNING)} and len(found) == 1


def test_failures_are_never_reported_as_passed(with_script, monkeypatch):
    fake = FakeBrowser(fail=True)
    found, executed = run(fake, monkeypatch)
    assert found == [] and all(executed[cid] == "skipped:tool_failed" for cid in IDS)
    assert len(fake.calls) == 1  # der Fehlschlag wird zwischengespeichert, kein zweiter Browser-Start
    _, executed = run(FakeBrowser(raw="not json"), monkeypatch)
    assert executed["BRW-CON-001"] == "skipped:tool_output_unreadable"
    _, executed = run(FakeBrowser(error="launch failed"), monkeypatch)
    assert executed["BRW-CON-001"] == "skipped:browser_failed"
    _, executed = run(FakeBrowser([CLEAN]), monkeypatch, components=lambda name: False)
    assert executed["BRW-CON-001"] == "skipped:component_missing:node,playwright"
    no_axe = {**CLEAN, "axe": None}
    _, executed = run(FakeBrowser([no_axe]), monkeypatch)
    assert executed["BRW-AXE-001"] == "skipped:axe_failed" and executed["BRW-CON-001"] == "ran"


def test_missing_script_and_localhost_are_skipped(env, monkeypatch):
    _, executed = run(FakeBrowser([CLEAN]), monkeypatch)
    assert executed["BRW-CON-001"] == "skipped:tool_not_found"
    local = make_snap(target="http://localhost:8000", allow_localhost=True)
    _, executed = run(FakeBrowser([CLEAN]), monkeypatch, snap=local)
    assert executed["BRW-CON-001"] == "skipped:localhost"


def test_sample_size_and_selection():
    snap = make_snap(count=40)
    snap.pages.append(Page(url="https://example.com/err", depth=2, status=404, html="<html></html>"))
    urls = _browser.sample_urls(snap)
    assert len(urls) == 10 and urls[0] == "https://example.com/"
    snap.profile = "deep"
    assert len(_browser.sample_urls(snap)) == 25
    assert all(not u.endswith("/err") for u in _browser.sample_urls(snap))


def test_ip_pinning_needs_a_verified_public_address(monkeypatch):
    class FakeDoh:
        answers = {"A": ["93.184.216.34"], "AAAA": []}

        def _query(self, name, rtype):
            return self.answers[rtype]

    monkeypatch.setattr(_browser, "DohResolver", FakeDoh)
    assert _browser._pin_ip(make_snap()) == "93.184.216.34"
    FakeDoh.answers = {"A": ["93.184.216.34"], "AAAA": ["::1"]}
    with pytest.raises(CheckSkipped):
        _browser._pin_ip(make_snap())
    FakeDoh.answers = {"A": [], "AAAA": ["2001:db8::1"]}
    with pytest.raises(CheckSkipped):
        _browser._pin_ip(make_snap())


def test_browser_script_keeps_the_safety_rules():
    root = Path(__file__).resolve().parent.parent
    text = (root / "src" / "claudios" / "components" / "npm" / "browser_probe.js").read_text("utf-8")
    assert "ignoreHTTPSErrors" not in text and "bypassCSP" not in text
    assert 'serviceWorkers: "block"' in text and "insecure_blocked" in text and "--host-resolver-rules" in text


LOCK = json.dumps({"lockfileVersion": 3, "packages": {"": {}, "node_modules/playwright": {"version": "1.49.0"}}}).encode()


@pytest.fixture
def fake_pw(env, monkeypatch):
    state = {"lock": LOCK}

    def resource(name):
        if name == "pw-package-lock.json":
            if state["lock"] is None:
                raise FileNotFoundError(name)
            return state["lock"]
        return b"{}"

    node_dir = paths.tools_dir() / "node"
    (node_dir / "node_modules" / "npm" / "bin").mkdir(parents=True)
    (node_dir / "node.exe").write_bytes(b"x")
    (node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js").write_text("//", "utf-8")
    monkeypatch.setattr(playwrighttools, "_resource_bytes", resource)
    monkeypatch.setattr(playwrighttools, "_node_exe", lambda: node_dir / "node.exe")
    return state


def pw_runner(calls, ci_code=0, install_code=0):
    def fake(args, *, cwd, timeout=None, root=None, extra_env=None):
        args = [str(a) for a in args]
        calls.append((args, extra_env))
        if "ci" in args:
            cli = Path(cwd) / "node_modules" / "playwright"
            cli.mkdir(parents=True)
            (cli / "cli.js").write_text("//", "utf-8")
            return ToolResult(ci_code, "", "", False)
        browsers = Path(extra_env["PLAYWRIGHT_BROWSERS_PATH"]) / "chromium-1"
        browsers.mkdir(parents=True)
        (browsers / "f").write_text("x", "utf-8")
        return ToolResult(install_code, "", "", False)
    return fake


def test_playwright_install_uses_the_lock_file_then_downloads_the_browser(fake_pw, monkeypatch):
    calls: list = []
    monkeypatch.setattr(playwrighttools, "run_tool", pw_runner(calls))
    assert manager.status(PLAYWRIGHT) == "missing"
    manager.install(PLAYWRIGHT)
    assert manager.status(PLAYWRIGHT) == "installed"
    (ci_args, _), (browser_args, browser_env) = calls
    assert "--ignore-scripts" in ci_args and "https://registry.npmjs.org/" in ci_args
    assert browser_args[-2:] == ["install", "chromium"] and "PLAYWRIGHT_BROWSERS_PATH" in browser_env
    assert (paths.tools_dir() / "playwright" / "browser_probe.js").is_file()
    assert manager.component_checker(lock=[PLAYWRIGHT])("playwright") is True
    fake_pw["lock"] = json.dumps({"packages": {"node_modules/other": {}}}).encode()
    assert manager.status(PLAYWRIGHT) == "outdated"
    fake_pw["lock"] = LOCK
    shutil.rmtree(paths.tools_dir() / "playwright" / "browsers")
    assert manager.status(PLAYWRIGHT) == "missing"
    assert list(paths.cache_dir().glob("tmp*")) == []


def test_playwright_install_refuses_unpinned_missing_node_and_failures(fake_pw, monkeypatch):
    for codes in ({"ci_code": 1}, {"install_code": 1}):
        calls: list = []
        monkeypatch.setattr(playwrighttools, "run_tool", pw_runner(calls, **codes))
        with pytest.raises(ClaudiosError) as e:
            manager.install(PLAYWRIGHT)
        assert e.value.code == E.TOOL_FAILED and not (paths.tools_dir() / "playwright").exists()
    monkeypatch.setattr(playwrighttools, "_node_exe", lambda: None)
    with pytest.raises(ClaudiosError) as e:
        manager.install(PLAYWRIGHT)
    assert e.value.code == E.COMPONENT_MISSING
    fake_pw["lock"] = None
    assert manager.status(PLAYWRIGHT) == "not_pinned"
    with pytest.raises(ClaudiosError) as e:
        manager.install(PLAYWRIGHT)
    assert e.value.code == E.COMPONENT_NOT_PINNED


def test_playwright_is_part_of_the_lock_before_npm_tools():
    names = [c.name for c in load_lock()]
    assert "playwright" in names and names.index("playwright") < names.index("npm-tools")
    assert PLAYWRIGHT.kind == "playwright" and PLAYWRIGHT.depends == ("node",)
    assert not PLAYWRIGHT.url and not PLAYWRIGHT.sha256
