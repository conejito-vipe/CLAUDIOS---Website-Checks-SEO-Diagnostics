import json
from pathlib import Path

import pytest

from claudios import paths
from claudios.checks import npmchecks
from claudios.components import manager, npmtools
from claudios.components.lock import NPM_TOOLS, load_lock
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult

PAGE = ('<html><head><script src="/app.js"></script><style>a{color:red}</style></head>'
        "<body><script>var x = 1;</script></body></html>")
ASSETS = {"css": [{"url": "https://example.com/a.css", "status": 200, "error": None, "text": "a{color:#ggg}"}],
          "js": [{"url": "https://example.com/app.js", "status": 200, "error": None, "text": "eval(x);"}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def make_snap(with_assets=True):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html=PAGE, content_type="text/html"))
    if with_assets:
        snap.extra["assets"] = ASSETS
    snap.status = "complete"
    return snap


class FakeTools:
    def __init__(self, eslint="[]", stylelint="[]", retire='{"data": []}', codes=None):
        self.outputs = {"eslint": eslint, "stylelint": stylelint, "retire": retire}
        self.codes = codes or {}
        self.calls = []

    def __call__(self, args, *, cwd, timeout=None, root=None, extra_env=None):
        args = [str(a) for a in args]
        self.calls.append(args)
        if "stylelint" in args[1]:
            Path(args[args.index("--output-file") + 1]).write_text(self.outputs["stylelint"], "utf-8")
            return ToolResult(self.codes.get("stylelint", 2), "", "", False)
        if "retire" in args[1]:
            Path(args[args.index("--outputpath") + 1]).write_text(self.outputs["retire"], "utf-8")
            return ToolResult(self.codes.get("retire", 0), "", "", False)
        return ToolResult(self.codes.get("eslint", 1), self.outputs["eslint"], "", False)

    def call_of(self, tool):
        """Der Aufruf eines bestimmten Werkzeugs (es laufen mehrere Prüfungen mit demselben Fake)."""
        return next(c for c in self.calls if tool in c[1])


def patch(monkeypatch, fake):
    monkeypatch.setattr(npmchecks, "tool_path", lambda name: Path("/t") / "node.exe")
    monkeypatch.setattr(npmchecks, "_script", lambda rel: Path("/npm") / rel)
    monkeypatch.setattr(npmchecks, "run_tool", fake)


def run(prefix, snap=None, components=lambda name: True):
    found, executed = run_checks(snap or make_snap(), 1, "standard", components=components)
    return [f for f in found if f.check_id.startswith(prefix)], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def test_eslint_results_are_mapped_and_tools_never_get_an_address(env, monkeypatch):
    out = json.dumps([
        {"filePath": "/x/f0.js", "messages": [
            {"ruleId": "security/detect-unsafe-regex", "severity": 1, "message": "bad regex", "line": 3},
            {"ruleId": "security/detect-non-literal-regexp", "severity": 1, "message": "dyn", "line": 2}]},
        {"filePath": "/x/f1.js", "messages": [
            {"ruleId": None, "fatal": True, "severity": 2, "message": "Parsing error", "line": 1}]}])
    fake = FakeTools(eslint=out)
    patch(monkeypatch, fake)
    found, executed = run("JSS-ESL", components=lambda name: True)
    assert pairs(found) == {("JSS-ESL-001", S.WARNING), ("JSS-ESL-001", S.NOTE), ("JSS-ESL-001", S.INFO)}
    warn = next(f for f in found if f.severity == S.WARNING)
    assert warn.url == "https://example.com/app.js" and warn.evidence == "Line 3: bad regex"
    assert executed["JSS-ESL-001"] == "ran"
    args = fake.call_of("eslint")
    assert "-c" in args and "--format" in args
    assert not any(a.startswith("https:") for call in fake.calls for a in call)


def test_stylelint_results_and_config_problems(env, monkeypatch):
    out = json.dumps([
        {"source": "/x/f0.css", "invalidOptionWarnings": [], "warnings": [
            {"rule": "color-no-invalid-hex", "text": "invalid hex", "line": 1, "severity": "error"},
            {"rule": "no-duplicate-selectors", "text": "dup", "line": 2, "severity": "error"}]},
        {"source": "/x/f1.css", "invalidOptionWarnings": [], "warnings": [
            {"rule": "CssSyntaxError", "text": "Unclosed block", "line": 1, "severity": "error"}]}])
    patch(monkeypatch, FakeTools(stylelint=out))
    found, executed = run("CSS-STY")
    assert pairs(found) == {("CSS-STY-001", S.WARNING), ("CSS-STY-001", S.NOTE), ("CSS-STY-001", S.INFO)}
    assert executed["CSS-STY-001"] == "ran"
    broken = json.dumps([{"source": "/x/f0.css", "warnings": [],
                          "invalidOptionWarnings": [{"text": "Unknown rule x"}]}])
    patch(monkeypatch, FakeTools(stylelint=broken))
    _, executed = run("CSS-STY")
    assert executed["CSS-STY-001"] == "skipped:tool_failed"


def test_retire_reports_the_worst_severity_per_library(env, monkeypatch):
    out = json.dumps({"data": [{"file": "/x/f0.js", "results": [
        {"component": "jquery", "version": "1.8.0", "vulnerabilities": [
            {"severity": "medium", "identifiers": {"CVE": ["CVE-2012-6708"]}},
            {"severity": "high", "identifiers": {"CVE": ["CVE-2015-9251"]}}]},
        {"component": "clean", "version": "1.0.0", "vulnerabilities": []}]}]})
    patch(monkeypatch, FakeTools(retire=out))
    found, executed = run("JSS-RET")
    assert len(found) == 1 and found[0].severity == S.ERROR
    assert "jquery 1.8.0" in found[0].msg_en and found[0].evidence == "CVE-2012-6708"
    assert executed["JSS-RET-001"] == "ran"


def test_failures_and_unreadable_output_are_never_passed(env, monkeypatch):
    patch(monkeypatch, FakeTools(retire="not json"))
    _, executed = run("JSS-RET")
    assert executed["JSS-RET-001"] == "skipped:tool_output_unreadable"
    patch(monkeypatch, FakeTools(codes={"retire": 1, "eslint": 2}))
    _, executed = run("JSS-RET")
    assert executed["JSS-RET-001"] == "skipped:tool_failed" and executed["JSS-ESL-001"] == "skipped:tool_failed"


def test_missing_components_and_missing_asset_data_are_skipped(env, monkeypatch):
    patch(monkeypatch, FakeTools())
    _, executed = run("JSS-", components=lambda name: name == "java")
    for cid in ("JSS-ESL-001", "CSS-STY-001", "JSS-RET-001"):
        assert executed[cid] == "skipped:component_missing:node,npm-tools"
    _, executed = run("JSS-", snap=make_snap(with_assets=False))
    for cid in ("JSS-ESL-001", "CSS-STY-001", "JSS-RET-001"):
        assert executed[cid] == "skipped:no_asset_data"


def lock_json():
    return json.dumps({"lockfileVersion": 3, "packages": {"": {}, "node_modules/eslint": {"version": "9.0.0"}}}).encode()


@pytest.fixture
def fake_npm(env, monkeypatch):
    state = {"lock": lock_json()}

    def resource(name):
        if name == "package-lock.json":
            if state["lock"] is None:
                raise FileNotFoundError(name)
            return state["lock"]
        return b"{}"

    node_dir = paths.tools_dir() / "node"
    (node_dir / "node_modules" / "npm" / "bin").mkdir(parents=True)
    (node_dir / "node.exe").write_bytes(b"x")
    (node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js").write_text("//", "utf-8")
    monkeypatch.setattr(npmtools, "_resource_bytes", resource)
    monkeypatch.setattr(npmtools, "_node_exe", lambda: node_dir / "node.exe")
    return state


def npm_runner(calls, code=0):
    def fake(args, *, cwd, timeout=None, root=None, extra_env=None):
        calls.append([str(a) for a in args])
        script = Path(cwd) / "node_modules" / "eslint" / "bin"
        script.mkdir(parents=True)
        (script / "eslint.js").write_text("//", "utf-8")
        return ToolResult(code, "", "", False)
    return fake


def test_npm_install_uses_the_lock_file_safely(fake_npm, monkeypatch):
    calls: list = []
    monkeypatch.setattr(npmtools, "run_tool", npm_runner(calls))
    assert manager.status(NPM_TOOLS) == "missing"
    manager.install(NPM_TOOLS)
    assert manager.status(NPM_TOOLS) == "installed"
    args = calls[0]
    assert "ci" in args and "--ignore-scripts" in args and "https://registry.npmjs.org/" in args
    assert (paths.tools_dir() / "npm-tools" / "package-lock.json").is_file()
    assert manager.component_checker(lock=[NPM_TOOLS])("npm-tools") is True
    fake_npm["lock"] = json.dumps({"packages": {"node_modules/other": {}}}).encode()
    assert manager.status(NPM_TOOLS) == "outdated"
    assert list(paths.cache_dir().glob("tmp*")) == []


def test_npm_install_refuses_unpinned_missing_node_and_failures(fake_npm, monkeypatch):
    calls: list = []
    monkeypatch.setattr(npmtools, "run_tool", npm_runner(calls, code=1))
    with pytest.raises(ClaudiosError) as e:
        manager.install(NPM_TOOLS)
    assert e.value.code == E.TOOL_FAILED and not (paths.tools_dir() / "npm-tools").exists()
    monkeypatch.setattr(npmtools, "_node_exe", lambda: None)
    with pytest.raises(ClaudiosError) as e:
        manager.install(NPM_TOOLS)
    assert e.value.code == E.COMPONENT_MISSING
    fake_npm["lock"] = None
    assert manager.status(NPM_TOOLS) == "not_pinned"
    with pytest.raises(ClaudiosError) as e:
        manager.install(NPM_TOOLS)
    assert e.value.code == E.COMPONENT_NOT_PINNED and calls == [calls[0]]


def test_npm_component_is_part_of_the_lock():
    lock = load_lock()
    assert lock[-1].name == "npm-tools" and lock[-1].kind == "npm" and lock[-1].depends == ("node",)
