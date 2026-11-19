import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from claudios.checks import load_all
from claudios.checks._util import CheckSkipped
from claudios.components import manager, playwrighttools, pwbrowserstools
from claudios.components.lock import load_lock
from claudios.core import foreign, probe_engines
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.registry import REGISTRY
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolbudget import classify
from claudios.core.toolrunner import ToolResult
from claudios.i18n.strings import TEXTS

URL = "https://example.com/"
URL2 = "https://example.com/two"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def snap_of(profile="deep"):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile=profile)
    snap.pages.append(Page(url=URL, depth=1, status=200, html="<html></html>", content_type="text/html"))
    snap.status = "complete"
    return snap


def look(host, rtype):
    return {"evil.test": {"A": ["10.0.0.5"]}, "cdn.test": {"A": ["8.8.8.8"]}}.get(host, {}).get(rtype, [])


def engine(name, pages, error=None):
    return {"engine": name, "version": "1", "error": error, "pages": pages}


def test_the_script_keeps_the_safety_rules_and_counts_as_a_browser_run():
    text = (Path(probe_engines.__file__).parent.parent / "components" / "npm" / "engine_probe.js").read_text("utf-8")
    assert 'serviceWorkers: "block"' in text and "isLocalName" in text and "firefox" in text and "webkit" in text
    assert "ignoreHTTPSErrors" not in text and "host-resolver-rules" not in text
    assert classify(["node", "C:\\x\\engine_probe.js", "in.json"]) == "browser"
    assert LIMITS.tool_runs_per_kind >= 4


def test_unexpected_tool_output_is_rejected_or_cleaned():
    assert probe_engines.clean(None) is None and probe_engines.clean({"engines": 5}) is None
    assert probe_engines.clean({"engines": [{"engine": "chrome", "pages": []}, 7]}) is None
    cleaned = probe_engines.clean({"engines": [{"engine": "firefox", "version": "1" * 50, "pages": [1, {"url": URL}]}]})
    assert len(cleaned["engines"][0]["version"]) == 20 and cleaned["engines"][0]["pages"] == [{"url": URL}]
    assert probe_engines.finish({"engines": [engine("firefox", [], error="x"), engine("webkit", [], error="y")]},
                                look) == {"skip": "browser_failed"}
    assert probe_engines.finish("junk") == {"skip": "tool_output_unreadable"}


def test_data_of_hosts_with_a_non_public_address_is_discarded():
    pages = [{"url": URL, "third_party": {"evil.test": 2, "cdn.test": 1},
              "failed": [{"url": "https://evil.test/a.js"}, {"url": "https://cdn.test/b.js"}]}]
    result = probe_engines.finish({"engines": [engine("firefox", pages)]}, look)
    page = result["engines"][0]["pages"][0]
    assert result["skip"] is None and result["foreign_private"] == ["evil.test"]
    assert page["third_party"] == {"cdn.test": 1} and [f["url"] for f in page["failed"]] == ["https://cdn.test/b.js"]


async def test_the_probe_runs_only_in_the_deep_profile_and_checks_the_resolution(monkeypatch):
    ran = []
    monkeypatch.setattr(probe_engines, "_run", lambda snap: ran.append(1) or {"skip": None, "engines": []})
    shallow = SimpleNamespace(profile="standard", target=SimpleNamespace(loopback=False))
    assert await probe_engines.collect(None, shallow, None) == {"skip": "profile_not_deep"} and ran == []
    local = SimpleNamespace(profile="deep", target=SimpleNamespace(loopback=True))
    assert await probe_engines.collect(None, local, None) == {"skip": "localhost"}
    deep = SimpleNamespace(profile="deep", target=SimpleNamespace(loopback=False))
    assert await probe_engines.collect(None, deep, None) == {"skip": None, "engines": []}

    async def flipped(gk):
        return False

    monkeypatch.setattr(probe_engines, "_unchanged", flipped)
    assert await probe_engines.collect(None, deep, None) == {"skip": "dns_changed"}


def test_run_writes_the_input_runs_the_script_and_cleans_the_output(env, monkeypatch):
    seen = {}
    monkeypatch.setattr(probe_engines, "_node", lambda: Path("/t/node/node.exe"))
    monkeypatch.setattr(probe_engines, "_environment", lambda node: {})
    monkeypatch.setattr(foreign, "lookup", look)

    def fake(args, **kwargs):
        seen["payload"] = json.loads(Path(args[2]).read_text("utf-8"))
        seen["script"] = Path(args[1]).read_text("utf-8")
        seen["timeout"] = kwargs["timeout"]
        page = {"url": URL, "third_party": {"evil.test": 1, "cdn.test": 2}}
        Path(args[3]).write_text(json.dumps({"engines": [engine("firefox", [page])]}), "utf-8")

    monkeypatch.setattr(probe_engines, "run_tool", fake)
    result = probe_engines._run(snap_of())
    assert seen["payload"]["urls"] == [URL] and "firefox" in seen["script"] and seen["timeout"] <= 1800.0
    assert result["skip"] is None and result["foreign_private"] == ["evil.test"]
    assert result["engines"][0]["pages"][0]["third_party"] == {"cdn.test": 2}

    def broken(args, **kwargs):
        raise ClaudiosError(E.TOOL_FAILED, reason="x")

    monkeypatch.setattr(probe_engines, "run_tool", broken)
    assert probe_engines._run(snap_of()) == {"skip": "tool_failed"}
    monkeypatch.setattr(probe_engines, "_node", lambda: None)
    assert probe_engines._run(snap_of()) == {"skip": "tool_not_found"}


def _check(extra):
    load_all()
    snap = SimpleNamespace(target=SimpleNamespace(url=URL), extra=extra)
    return REGISTRY["BRW-ENG-001"].fn(snap)


BASE = {"pages": [{"url": URL, "error": None, "page_errors": [], "overflow": {"360": False}},
                  {"url": URL2, "error": None, "page_errors": [], "overflow": {"360": False}}]}


def test_the_check_reports_differences_to_chromium():
    pages = [{"url": URL, "error": "net::ERR_FAILED"},
             {"url": URL2, "error": None, "page_errors": ["boom"], "overflow": {"360": True}}]
    data = {"skip": None, "engines": [engine("firefox", pages), engine("webkit", [], error="launch failed")]}
    found = _check({"engines": data, "browser": BASE})
    assert sorted(f.severity for f in found) == [S.INFO, S.NOTE, S.NOTE, S.WARNING]
    assert any(f.severity == S.WARNING and "Firefox" in f.msg_en for f in found)


def test_the_check_is_quiet_when_chromium_shows_the_same_and_skips_without_data():
    pages = [{"url": URL, "error": None, "page_errors": ["boom"], "overflow": {"360": True}}]
    same = {"pages": [{"url": URL, "error": None, "page_errors": ["boom"], "overflow": {"360": True}}]}
    assert _check({"engines": {"skip": None, "engines": [engine("webkit", pages)]}, "browser": same}) == []
    with pytest.raises(CheckSkipped) as error:
        _check({})
    assert error.value.reason == "no_engine_data"
    with pytest.raises(CheckSkipped) as error:
        _check({"engines": {"skip": "profile_not_deep"}})
    assert error.value.reason == "profile_not_deep"
    with pytest.raises(CheckSkipped) as error:
        _check({"engines": {"skip": None, "engines": [engine("firefox", [], error="x")]}})
    assert error.value.reason == "engines_failed"


def test_the_check_never_runs_in_standard_and_needs_the_component_in_deep():
    snap = snap_of("standard")
    _, executed = run_checks(snap, 1, "standard")
    assert "BRW-ENG-001" not in executed
    _, executed = run_checks(snap_of("deep"), 1, "deep")
    assert executed["BRW-ENG-001"].startswith("skipped:component_missing:") and "pw-browsers" in executed["BRW-ENG-001"]


def test_the_foreign_host_check_also_reads_the_engine_data():
    load_all()
    snap = SimpleNamespace(target=SimpleNamespace(url=URL), extra={
        "browser": {"error_reason": "tool_not_found", "pages": []},
        "engines": {"skip": None, "engines": [], "foreign_private": ["evil.test"]}})
    found = REGISTRY["BRW-FRN-001"].fn(snap)
    assert len(found) == 1 and found[0].evidence == "Firefox/WebKit"


def test_the_browser_component_has_its_own_installer_and_comes_after_playwright():
    comps = load_lock()
    names = [c.name for c in comps]
    comp = comps[names.index("pw-browsers")]
    assert names.index("pw-browsers") > names.index("playwright") and names[-1] == "npm-tools"
    assert comp.depends == ("playwright",) and manager._handler(comp.kind) is pwbrowserstools


def test_status_needs_the_pinned_lock_and_both_engines(env, monkeypatch):
    comp = next(c for c in load_lock() if c.name == "pw-browsers")
    root = env / "tools"
    monkeypatch.setattr(playwrighttools, "lock_hash", lambda: "")
    assert pwbrowserstools.status(comp, root) == "not_pinned"
    monkeypatch.setattr(playwrighttools, "lock_hash", lambda: "a" * 64)
    assert pwbrowserstools.status(comp, root) == "missing"
    for name in ("firefox-1", "webkit-2"):
        (root / "playwright" / "browsers" / name).mkdir(parents=True)
    base = root / comp.name
    base.mkdir(parents=True)
    (base / pwbrowserstools.MARKER).write_text(json.dumps({"sha256": "a" * 64}), "utf-8")
    assert pwbrowserstools.status(comp, root) == "installed"
    monkeypatch.setattr(playwrighttools, "lock_hash", lambda: "b" * 64)
    assert pwbrowserstools.status(comp, root) == "outdated"


def test_install_runs_the_playwright_cli_for_both_engines(env, monkeypatch):
    root = env / "tools"
    cli = root / "playwright" / "node_modules" / "playwright" / "cli.js"
    node = root / "node" / "node.exe"
    comp = next(c for c in load_lock() if c.name == "pw-browsers")
    monkeypatch.setattr(pwbrowserstools, "_node", lambda: node)
    monkeypatch.setattr(pwbrowserstools, "node_env", lambda folder: {})
    monkeypatch.setattr(playwrighttools, "lock_hash", lambda: "c" * 64)
    with pytest.raises(ClaudiosError) as error:
        pwbrowserstools.install(comp, root=root)
    assert error.value.code == E.COMPONENT_MISSING
    cli.parent.mkdir(parents=True)
    cli.write_text("x", "utf-8")
    calls = []

    def fake(args, **kwargs):
        calls.append((args, kwargs))
        for name in ("firefox-1", "webkit-1"):
            (root / "playwright" / "browsers" / name).mkdir(parents=True, exist_ok=True)
        return ToolResult(0, "", "", False)

    monkeypatch.setattr(pwbrowserstools, "run_tool", fake)
    pwbrowserstools.install(comp, root=root)
    args, kwargs = calls[0]
    assert args[2:] == ["install", "firefox", "webkit"] and kwargs["extra_env"]["PLAYWRIGHT_BROWSERS_PATH"].endswith("browsers")
    assert pwbrowserstools.status(comp, root) == "installed"


def test_texts_exist_in_both_languages():
    assert TEXTS["de"]["probe.engines"].strip() and TEXTS["en"]["probe.engines"].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
