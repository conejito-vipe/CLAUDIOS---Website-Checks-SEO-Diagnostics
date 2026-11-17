import json
from pathlib import Path

import httpx
import pytest

from claudios import paths
from claudios.core import probe_zap
from claudios.core.engine import run_checks
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.probes import _extension_steps
from claudios.core.snapshot import Page, Snapshot
from claudios.i18n.strings import TEXTS

PEM = b"-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"
ALERTS = [
    {"alert": "Missing Anti-clickjacking Header", "risk": "Medium", "url": "https://example.com/",
     "cweid": "1021", "pluginId": "10020", "evidence": "sessionid=SECRETVAL"},
    {"alert": "Missing Anti-clickjacking Header", "risk": "Medium", "url": "https://example.com/a",
     "cweid": "1021", "pluginId": "10020", "evidence": "sessionid=SECRETVAL"},
    {"alert": "Cookie without SameSite Attribute", "risk": "Low", "url": "https://example.com/",
     "cweid": "1275", "pluginId": "10054"},
    {"alert": "Serious Thing", "risk": "High", "url": "https://example.com/x", "cweid": "-1", "pluginId": "1"},
    {"alert": "Just Info", "risk": "Informational", "url": "https://example.com/", "cweid": "0", "pluginId": "2"},
    {"alert": "Foreign", "risk": "High", "url": "https://tracker.other.test/", "cweid": "1", "pluginId": "3"},
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def make_snap(level=2, status=200, target="example.com", allow_localhost=False):
    snap = Snapshot(target=normalize_input(target, allow_localhost), level=level, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=status, html="<html></html>",
                           content_type="text/html"))
    snap.status = "complete"
    return snap


class FakeProc:
    def __init__(self, alive=True):
        self.alive, self.stopped = alive, False

    def poll(self):
        return None if self.alive and not self.stopped else 1

    def terminate(self):
        self.stopped = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.stopped = True


def api(alerts=None, scanners=3, records=("0",)):
    state = {"records": list(records), "paths": []}

    def handler(request):
        path = request.url.path
        state["paths"].append(path)
        if path.endswith("/core/view/version/"):
            return httpx.Response(200, json={"version": "2.17.0"})
        if path.endswith("/pscan/view/scanners/"):
            return httpx.Response(200, json={"scanners": [{"id": str(i)} for i in range(scanners)]})
        if path.endswith("/core/other/rootcert/"):
            return httpx.Response(200, content=PEM)
        if path.endswith("/pscan/view/recordsToScan/"):
            value = state["records"].pop(0) if len(state["records"]) > 1 else state["records"][0]
            return httpx.Response(200, json={"recordsToScan": value})
        if path.endswith("/core/view/alerts/"):
            return httpx.Response(200, json={"alerts": alerts or []})
        return httpx.Response(404)

    return handler, state


def setup(monkeypatch, handler, proc=None, tools=True, browse=None):
    rec = {"starts": [], "browse": [], "proc": proc or FakeProc()}
    monkeypatch.setattr(probe_zap, "_tools", (
        lambda: (Path("/t/java.exe"), Path("/t/zap/zap-2.17.0.jar"), Path("/t/node.exe"))) if tools else (lambda: None))
    monkeypatch.setattr(probe_zap, "_free_port", lambda: 8090)

    def start(java, jar, home, port, key):
        rec["starts"].append((port, key, Path(home).is_dir()))
        return rec["proc"]

    def fake_browse(node, home, payload):
        rec["browse"].append({**payload, "cert_text": Path(payload["cert_path"]).read_text("utf-8")})
        return browse or {"browser": "1", "error": None,
                          "pages": [{"url": u, "status": 200, "error": None} for u in payload["urls"]]}

    monkeypatch.setattr(probe_zap, "_start_zap", start)
    monkeypatch.setattr(probe_zap, "_client", lambda port, key: httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://zap.test", headers={"X-ZAP-API-KEY": key}))
    monkeypatch.setattr(probe_zap, "_browse", fake_browse)
    monkeypatch.setattr(probe_zap, "_pause", lambda seconds: None)
    return rec


async def run(snap):
    snap.extra["zap"] = await probe_zap.collect(None, snap, None)
    found, executed = run_checks(snap, snap.level, "standard", components=lambda name: True)
    return [f for f in found if f.check_id == "ZAP-PAS-001"], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


async def test_alerts_are_mapped_filtered_and_cleaned_up(env, monkeypatch):
    handler, state = api(alerts=ALERTS, records=("3", "0"))
    rec = setup(monkeypatch, handler)
    snap = make_snap()
    found, executed = await run(snap)
    assert pairs(found) == {("ZAP-PAS-001", S.ERROR), ("ZAP-PAS-001", S.WARNING), ("ZAP-PAS-001", S.NOTE),
                            ("ZAP-PAS-001", S.INFO)}
    assert len(found) == 4 and executed["ZAP-PAS-001"] == "ran"
    medium = next(f for f in found if f.severity == S.WARNING)
    assert "Anti-clickjacking" in medium.msg_en and "(2x)" in medium.msg_en and "CWE-1021" in medium.evidence
    assert not any("Foreign" in f.msg_en for f in found)  # Fremdserver sind gefiltert
    assert "SECRETVAL" not in json.dumps(snap.extra["zap"]) and "SECRETVAL" not in repr(found)
    assert rec["proc"].stopped
    port, key, home_existed = rec["starts"][0]
    assert port == 8090 and len(key) == 32 and home_existed
    payload = rec["browse"][0]
    assert payload["proxy_port"] == 8090 and payload["urls"] == ["https://example.com/"]
    assert payload["cert_text"].startswith("-----BEGIN CERTIFICATE-----")
    assert not any("ascan" in p or "spider" in p for p in state["paths"])  # nie ein aktiver Scan
    assert list(paths.cache_dir().glob("tmp*")) == []  # der aufgezeichnete Verkehr ist gelöscht


async def test_the_probe_and_the_check_only_run_at_level_2(env, monkeypatch):
    handler, _ = api()
    rec = setup(monkeypatch, handler)
    names1 = [name for name, _make in _extension_steps(None, make_snap(level=1), None)]
    names2 = [name for name, _make in _extension_steps(None, make_snap(level=2), None)]
    assert "zap" not in names1 and "paths" not in names1 and {"zap", "paths"} <= set(names2)
    _, executed = run_checks(make_snap(level=1), 1, "standard", components=lambda name: True)
    assert executed["ZAP-PAS-001"] == "skipped:level2_required"
    assert rec["starts"] == []


@pytest.mark.parametrize("case,reason", [
    ("no_rules", "zap_no_passive_rules"), ("dead", "zap_start_failed"), ("browser", "browser_failed"),
    ("tools", "tool_not_found"), ("localhost", "localhost"), ("pages", "no_pages")])
async def test_failures_are_never_reported_as_passed(env, monkeypatch, case, reason):
    handler, _ = api(scanners=0 if case == "no_rules" else 3)
    browse = {"browser": "", "error": "launch failed", "pages": []} if case == "browser" else None
    rec = setup(monkeypatch, handler, proc=FakeProc(alive=case != "dead"), tools=case != "tools", browse=browse)
    snap = make_snap()
    if case == "localhost":
        snap = make_snap(target="http://localhost:8000", allow_localhost=True)
    if case == "pages":
        snap = make_snap(status=404)
    found, executed = await run(snap)
    assert found == [] and executed["ZAP-PAS-001"] == f"skipped:{reason}"
    if case in ("tools", "localhost", "pages"):
        assert rec["starts"] == []
    if case == "no_rules":
        assert rec["browse"] == [] and rec["proc"].stopped  # ohne Regeln wird gar nicht erst gebrowst
    assert list(paths.cache_dir().glob("tmp*")) == []


async def test_unfinished_passive_evaluation_is_reported(env, monkeypatch):
    handler, _ = api(records=("5",))
    setup(monkeypatch, handler)
    monkeypatch.setattr(probe_zap, "PASSIVE_WAIT", 0.0)
    found, executed = await run(make_snap())
    assert pairs(found) == {("ZAP-PAS-001", S.INFO)} and "not finished" in found[0].msg_en
    assert executed["ZAP-PAS-001"] == "ran"


def test_zap_is_started_locally_only_with_a_random_key():
    cmd = probe_zap.command(Path("/t/java.exe"), Path("/t/zap.jar"), Path("/h"), 8090, "k" * 32)
    assert "-daemon" in cmd and "-silent" in cmd and "127.0.0.1" in cmd and f"api.key={'k' * 32}" in cmd
    assert "0.0.0.0" not in " ".join(cmd) and cmd[0].endswith("java.exe")


def test_browser_script_pins_the_zap_certificate_and_keeps_the_safety_rules():
    root = Path(__file__).resolve().parent.parent
    text = (root / "src" / "claudios" / "components" / "npm" / "zap_probe.js").read_text("utf-8")
    assert "ignoreHTTPSErrors" not in text and "bypassCSP" not in text
    assert '"--ignore-certificate-errors"' not in text  # nur der SPKI-Pin, nie alle Fehler
    assert "--ignore-certificate-errors-spki-list=" in text and "spkiHash" in text
    assert 'serviceWorkers: "block"' in text and 'protocol === "http:"' in text and "isLocalName" in text


def test_zap_texts_exist_in_both_languages():
    for lang in ("de", "en"):
        assert TEXTS[lang]["probe.zap"].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
