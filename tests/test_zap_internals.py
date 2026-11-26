"""ZAP-Lauf im Einzelnen: Werkzeugsuche, Start ohne Geheimnisse in der Umgebung, Beenden, Zertifikat, Ausgabe-Prüfung, Aufräumen."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from claudios.core import probe_zap
from claudios.core.errors import ClaudiosError, ErrorCode as E


def client_for(handler):
    return httpx.Client(base_url="http://127.0.0.1:1", transport=httpx.MockTransport(handler))


class Proc:
    def __init__(self, alive=True, wait_raises=0):
        self.alive, self.wait_raises, self.calls = alive, wait_raises, []

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")

    def wait(self, timeout=None):
        self.calls.append("wait")
        if self.wait_raises > 0:
            self.wait_raises -= 1
            raise subprocess.TimeoutExpired("zap", timeout)


def test_tools_are_found_only_when_java_node_zap_and_playwright_are_all_there(tmp_path, monkeypatch):
    monkeypatch.setattr(probe_zap.paths, "tools_dir", lambda: tmp_path)
    monkeypatch.setattr(probe_zap, "tool_path", lambda name: tmp_path / name)
    assert probe_zap._tools() is None
    (tmp_path / "zap" / "ZAP_2.15").mkdir(parents=True)
    (tmp_path / "zap" / "ZAP_2.15" / "zap-2.15.0.jar").write_bytes(b"x")
    (tmp_path / "zap" / "ZAP_2.15" / "zap-extra-x.jar").write_bytes(b"x")  # kein Versionsname: wird ignoriert
    assert probe_zap._tools() is None  # Playwright fehlt noch
    (tmp_path / "playwright" / "node_modules" / "playwright").mkdir(parents=True)
    java, jar, node = probe_zap._tools()
    assert jar.name == "zap-2.15.0.jar" and java.name == "java" and node.name == "node"
    monkeypatch.setattr(probe_zap, "tool_path", lambda name: None if name == "java" else tmp_path / name)
    assert probe_zap._tools() is None


def test_the_free_port_is_a_local_unprivileged_port():
    assert 1024 <= probe_zap._free_port() <= 65535


def test_zap_starts_without_a_shell_and_with_a_minimal_environment(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(probe_zap, "ensure_in_tools", lambda _p: None)
    monkeypatch.setenv("GITHUB_TOKEN", "geheim-token-wert")
    monkeypatch.setenv("TEMP", "/tmp")

    def fake_popen(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return "proc"

    monkeypatch.setattr(probe_zap.subprocess, "Popen", fake_popen)
    assert probe_zap._start_zap(Path("/t/java"), Path("/t/zap.jar"), tmp_path, 8090, "k" * 32) == "proc"
    assert seen["shell"] is False and "GITHUB_TOKEN" not in seen["env"] and seen["env"].get("TEMP") == "/tmp"
    assert seen["stdin"] == subprocess.DEVNULL and "geheim-token-wert" not in json.dumps(seen["env"])


def test_a_start_error_means_skipped_not_crashed(tmp_path, monkeypatch):
    monkeypatch.setattr(probe_zap, "ensure_in_tools", lambda _p: None)
    monkeypatch.setattr(probe_zap.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("kein Java")))
    with pytest.raises(probe_zap._Skip) as info:
        probe_zap._start_zap(Path("/t/java"), Path("/t/zap.jar"), tmp_path, 1, "k")
    assert info.value.reason == "zap_start_failed"


def test_a_java_outside_the_tools_folder_is_refused(tmp_path, monkeypatch):
    def refuse(_p):
        raise ClaudiosError(E.TOOL_FAILED)

    monkeypatch.setattr(probe_zap, "ensure_in_tools", refuse)
    with pytest.raises(ClaudiosError):
        probe_zap._start_zap(Path("/evil/java"), Path("/t/zap.jar"), tmp_path, 1, "k")


def test_zap_is_stopped_politely_then_by_force_and_a_dead_process_is_left_alone():
    probe_zap._stop_zap(None)
    dead = Proc(alive=False)
    probe_zap._stop_zap(dead)
    assert dead.calls == []
    polite = Proc()
    probe_zap._stop_zap(polite)
    assert polite.calls == ["terminate", "wait"]
    stubborn = Proc(wait_raises=1)
    probe_zap._stop_zap(stubborn)
    assert stubborn.calls == ["terminate", "wait", "kill", "wait"]
    hopeless = Proc(wait_raises=2)
    probe_zap._stop_zap(hopeless)  # gibt nach dem zweiten Warten auf, ohne Ausnahme
    assert hopeless.calls[-1] == "wait"


def test_api_answers_that_are_not_json_objects_are_a_skip():
    for body in ("[1]", "kein json", '"text"'):
        client = client_for(lambda _r, b=body: httpx.Response(200, text=b))
        with pytest.raises(probe_zap._Skip):
            probe_zap._json(client, "/x")
    with pytest.raises(probe_zap._Skip):
        probe_zap._json(client_for(lambda _r: httpx.Response(500)), "/x")


def test_waiting_for_zap_gives_up_when_the_process_died_or_the_time_is_up(monkeypatch):
    monkeypatch.setattr(probe_zap, "_pause", lambda _s: None)
    with pytest.raises(probe_zap._Skip):
        probe_zap._wait_ready(client_for(lambda _r: httpx.Response(200, json={})), Proc(alive=False))
    monkeypatch.setattr(probe_zap, "READY_WAIT", 0.0)
    with pytest.raises(probe_zap._Skip):
        probe_zap._wait_ready(client_for(lambda _r: httpx.Response(503)), Proc())
    assert probe_zap._wait_ready(client_for(lambda _r: httpx.Response(200, json={"version": "2.15.0"})), Proc()) == "2.15.0"


def test_the_passive_wait_rejects_garbage_and_reports_unfinished_queues(monkeypatch):
    monkeypatch.setattr(probe_zap, "_pause", lambda _s: None)
    with pytest.raises(probe_zap._Skip):
        probe_zap._wait_passive(client_for(lambda _r: httpx.Response(200, json={"recordsToScan": "abc"})))
    monkeypatch.setattr(probe_zap, "PASSIVE_WAIT", 0.0)
    assert probe_zap._wait_passive(client_for(lambda _r: httpx.Response(200, json={"recordsToScan": "3"}))) is False
    assert probe_zap._wait_passive(client_for(lambda _r: httpx.Response(200, json={"recordsToScan": "0"}))) is True


def test_alerts_of_foreign_hosts_and_malformed_entries_are_dropped_and_urls_are_redacted():
    snap = SimpleNamespace(target=SimpleNamespace(host="www.example.com", registrable="example.com"))
    alerts = [{"alert": "Fehlt: CSP", "risk": "Medium", "url": "https://www.example.com/a?token=abc12345secret", "cweid": "693"},
              {"alert": "Tracker", "risk": "Low", "url": "https://tracker.evil.net/x"},
              "kein dict", {"name": "Sub", "url": "https://cdn.example.com/y"}]
    client = client_for(lambda _r: httpx.Response(200, json={"alerts": alerts}))
    out = probe_zap._alerts(client, snap)
    assert [a["name"] for a in out] == ["Fehlt: CSP", "Sub"] and "abc12345secret" not in json.dumps(out)
    assert probe_zap._alerts(client_for(lambda _r: httpx.Response(200, json={"alerts": "x"})), snap) == []


def test_seen_hosts_survive_garbage_and_errors():
    assert probe_zap._seen_hosts(client_for(lambda _r: httpx.Response(500))) == set()
    out = probe_zap._seen_hosts(client_for(lambda _r: httpx.Response(200, json={"hosts": ["https://A.example.com", 5, " b.example.net:8080 ", ""]})))
    assert out == {"a.example.com", "b.example.net"}


def session_env(monkeypatch, tmp_path, *, cert=b"-----BEGIN CERTIFICATE-----\nx", scanners=("a",), browser=None):
    def handler(request):
        path = request.url.path
        if path.endswith("/version/"):
            return httpx.Response(200, json={"version": "2.15.0"})
        if path.endswith("/scanners/"):
            return httpx.Response(200, json={"scanners": list(scanners)})
        if path.endswith("/rootcert/"):
            return httpx.Response(200, content=cert)
        return httpx.Response(200, json={})

    monkeypatch.setattr(probe_zap, "_browse", lambda *a: browser if browser is not None else {"pages": [1], "error": None})
    monkeypatch.setattr(probe_zap, "_wait_passive", lambda _c: True)
    monkeypatch.setattr(probe_zap, "_alerts", lambda *_a: [])
    monkeypatch.setattr(probe_zap, "_seen_hosts", lambda _c: set())
    monkeypatch.setattr(probe_zap, "_screen", lambda result, *_a: result)
    snap = SimpleNamespace(target=SimpleNamespace(host="example.com", registrable="example.com"))
    return client_for(handler), snap


def test_session_runs_only_with_passive_rules_and_a_real_certificate(monkeypatch, tmp_path):
    client, snap = session_env(monkeypatch, tmp_path)
    out = probe_zap._session(client, Proc(), snap, ["https://example.com/"], "node", tmp_path, 1)
    assert out["zap_version"] == "2.15.0" and out["pages"] == 1 and (tmp_path / "zap-root.pem").is_file()
    client, snap = session_env(monkeypatch, tmp_path, scanners=())
    with pytest.raises(probe_zap._Skip, match="zap_no_passive_rules"):
        probe_zap._session(client, Proc(), snap, ["u"], "node", tmp_path, 1)
    client, snap = session_env(monkeypatch, tmp_path, cert=b"<html>kein Zertifikat</html>")
    with pytest.raises(probe_zap._Skip, match="zap_api_failed"):
        probe_zap._session(client, Proc(), snap, ["u"], "node", tmp_path, 1)
    client, snap = session_env(monkeypatch, tmp_path, browser={"pages": [], "error": "x"})
    with pytest.raises(probe_zap._Skip, match="browser_failed"):
        probe_zap._session(client, Proc(), snap, ["u"], "node", tmp_path, 1)


def test_browser_output_must_be_a_json_object_with_a_page_list(monkeypatch, tmp_path):
    monkeypatch.setattr(probe_zap.paths, "tools_dir", lambda: tmp_path / "tools")
    monkeypatch.setattr(probe_zap, "node_env", lambda _p: {})
    payload = {"urls": ["https://example.com/"]}

    def runner(content):
        def run(cmd, **_kw):
            if content is not None:
                Path(cmd[-1]).write_text(content, "utf-8")
        return run

    for bad in (None, "kein json", "[]", '{"pages": "x"}'):
        monkeypatch.setattr(probe_zap, "run_tool", runner(bad))
        with pytest.raises(probe_zap._Skip, match="tool_output_unreadable"):
            probe_zap._browse("/n/node", tmp_path, payload)
    monkeypatch.setattr(probe_zap, "run_tool", runner('{"pages": [1, 2]}'))
    assert probe_zap._browse("/n/node", tmp_path, payload) == {"pages": [1, 2]}
    monkeypatch.setattr(probe_zap, "run_tool", lambda *a, **k: (_ for _ in ()).throw(ClaudiosError(E.TOOL_FAILED)))
    with pytest.raises(probe_zap._Skip, match="tool_failed"):
        probe_zap._browse("/n/node", tmp_path, payload)


def test_cleanup_retries_when_files_are_locked_and_then_gives_up(tmp_path, monkeypatch):
    pauses = []
    monkeypatch.setattr(probe_zap, "_pause", pauses.append)
    monkeypatch.setattr(probe_zap.shutil, "rmtree", lambda *_a, **_k: None)  # Ordner bleibt (Datei gesperrt)
    probe_zap._remove(tmp_path)
    assert len(pauses) == 5
    gone = tmp_path / "weg"
    pauses.clear()
    probe_zap._remove(gone)
    assert pauses == []
