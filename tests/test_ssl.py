import json
import sys
from pathlib import Path

import pytest

from claudios import paths
from claudios.checks import sslchecks
from claudios.checks._util import CheckSkipped
from claudios.components import manager, piptools
from claudios.components.extra_sslyze import COMPONENT as SSLYZE
from claudios.components.lock import load_lock
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolrunner import ToolResult

TARGET = sslchecks.TARGET_FORMAT.format(host="example.com", ip="93.184.216.34")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def make_snap():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html="<html></html>",
                           content_type="text/html"))
    snap.status = "complete"
    return snap


def suites(*names):
    return {"status": "COMPLETED", "result": {"accepted_cipher_suites": [{"cipher_suite": {"name": n}} for n in names]}}


GOOD_CERT = {"status": "COMPLETED", "result": {"certificate_deployments": [
    {"leaf_certificate_subject_matches_hostname": True,
     "path_validation_results": [{"was_validation_successful": True}]}]}}


def good_scan(**more):
    scan = {"ssl_2_0_cipher_suites": suites(), "ssl_3_0_cipher_suites": suites(), "tls_1_0_cipher_suites": suites(),
            "tls_1_1_cipher_suites": suites(), "tls_1_2_cipher_suites": suites("ECDHE-RSA-AES128-GCM-SHA256"),
            "tls_1_3_cipher_suites": suites("TLS_AES_256_GCM_SHA384"), "certificate_info": GOOD_CERT}
    scan.update(more)
    return scan


class FakeSslyze:
    def __init__(self, scan=None, status="COMPLETED", raw=None, fail=False):
        self.scan, self.status, self.raw, self.fail, self.calls = scan, status, raw, fail, []

    def __call__(self, args, *, cwd, timeout=None, root=None, extra_env=None):
        args = [str(a) for a in args]
        self.calls.append(args)
        if self.fail:
            raise ClaudiosError(E.TOOL_FAILED, reason="timeout")
        out = Path(args[args.index("--json_out") + 1])
        if self.raw is not None:
            out.write_text(self.raw, "utf-8")
        else:
            scan = self.scan if self.status == "COMPLETED" else None
            out.write_text(json.dumps({"server_scan_results": [{"scan_status": self.status, "scan_result": scan}]}),
                           "utf-8")
        return ToolResult(0, "", "", False)


def patch(monkeypatch, fake):
    monkeypatch.setattr(sslchecks, "tool_path", lambda name: Path("/t/sslyze/Scripts/python.exe"))
    monkeypatch.setattr(sslchecks, "_target", lambda snap: TARGET)
    monkeypatch.setattr(sslchecks, "run_tool", fake)


def run(prefix, fake, monkeypatch, level=1, components=lambda name: True):
    patch(monkeypatch, fake)
    found, executed = run_checks(make_snap(), level, "standard", components=components)
    return [f for f in found if f.check_id.startswith(prefix)], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def test_the_verified_target_notation_is_host_port_then_ip_in_braces():
    # Im Workflow "pip-Sperrliste" geprüft: host{ip}:443 scheitert mit Verbindungsfehler, host:443{ip} funktioniert.
    assert TARGET == "example.com:443{93.184.216.34}"


def test_old_protocols_weak_ciphers_and_missing_tls13_are_reported(env, monkeypatch):
    scan = good_scan(tls_1_0_cipher_suites=suites("AES128-SHA"),
                     tls_1_2_cipher_suites=suites("ECDHE-RSA-AES128-GCM-SHA256", "DES-CBC3-SHA"),
                     tls_1_3_cipher_suites=suites())
    fake = FakeSslyze(scan)
    found, executed = run("TLS-PRO", fake, monkeypatch)
    assert pairs(found) == {("TLS-PRO-001", S.WARNING), ("TLS-PRO-001", S.INFO)}
    assert len(found) == 3 and any("TLS 1.0" in f.msg_en for f in found)
    assert any("DES-CBC3-SHA" in f.evidence for f in found)
    assert executed["TLS-PRO-001"] == "ran"
    args = fake.calls[0]
    assert "--tlsv1" in args and "--json_out" in args and "--heartbleed" not in args
    assert args[-1] == TARGET


def test_modern_server_has_no_findings(env, monkeypatch):
    found, executed = run("TLS-PRO", FakeSslyze(good_scan()), monkeypatch)
    assert found == [] and executed["TLS-PRO-001"] == "ran"


def test_certificate_problems_and_no_modern_protocol_are_errors(env, monkeypatch):
    cert = {"status": "COMPLETED", "result": {"certificate_deployments": [
        {"leaf_certificate_subject_matches_hostname": False,
         "path_validation_results": [{"was_validation_successful": False}]}]}}
    found, _ = run("TLS-PRO", FakeSslyze(good_scan(certificate_info=cert)), monkeypatch)
    assert [f.severity for f in found] == [S.ERROR, S.ERROR]
    old = good_scan(tls_1_2_cipher_suites=suites(), tls_1_3_cipher_suites=suites())
    found, _ = run("TLS-PRO", FakeSslyze(old), monkeypatch)
    assert pairs(found) == {("TLS-PRO-001", S.ERROR)} and "neither TLS 1.2" in found[0].msg_en


def test_failures_are_never_reported_as_passed(env, monkeypatch):
    _, executed = run("TLS-PRO", FakeSslyze(status="ERROR_NO_CONNECTIVITY"), monkeypatch)
    assert executed["TLS-PRO-001"] == "skipped:tool_failed"
    _, executed = run("TLS-PRO", FakeSslyze(raw="not json"), monkeypatch)
    assert executed["TLS-PRO-001"] == "skipped:tool_output_unreadable"
    _, executed = run("TLS-PRO", FakeSslyze(scan={}), monkeypatch)
    assert executed["TLS-PRO-001"] == "skipped:tool_output_unreadable"
    _, executed = run("TLS-PRO", FakeSslyze(fail=True), monkeypatch)
    assert executed["TLS-PRO-001"] == "skipped:tool_failed"
    _, executed = run("TLS-PRO", FakeSslyze(good_scan()), monkeypatch, components=lambda name: False)
    assert executed["TLS-PRO-001"] == "skipped:component_missing:sslyze"


def test_attack_checks_run_only_at_level_2(env, monkeypatch):
    scan = {"heartbleed": {"status": "COMPLETED", "result": {"is_vulnerable_to_heartbleed": True}},
            "openssl_ccs_injection": {"status": "COMPLETED", "result": {"is_vulnerable_to_ccs_injection": False}},
            "robot": {"status": "COMPLETED", "result": {"robot_result": "VULNERABLE_STRONG_ORACLE"}}}
    fake = FakeSslyze(scan)
    # Stufe 1: die passive Prüfung darf laufen, aber kein Aufruf darf die aktiven Tests enthalten.
    found, executed = run("TLS-ATK", fake, monkeypatch, level=1)
    assert found == [] and executed["TLS-ATK-001"] == "skipped:level2_required"
    assert not any("--heartbleed" in call or "--robot" in call for call in fake.calls)
    fake.calls.clear()
    # Stufe 2: die aktive Prüfung läuft mit genau ihren Tests.
    found, executed = run("TLS-ATK", fake, monkeypatch, level=2)
    assert pairs(found) == {("TLS-ATK-001", S.CRITICAL), ("TLS-ATK-001", S.ERROR)} and len(found) == 2
    assert executed["TLS-ATK-001"] == "ran"
    attack = next(call for call in fake.calls if "--robot" in call)
    assert "--heartbleed" in attack and "--openssl_ccs" in attack and "--sslv2" not in attack
    clean = {"heartbleed": {"status": "COMPLETED", "result": {"is_vulnerable_to_heartbleed": False}},
             "robot": {"status": "COMPLETED", "result": {"robot_result": "NOT_VULNERABLE_NO_ORACLE"}}}
    found, executed = run("TLS-ATK", FakeSslyze(clean), monkeypatch, level=2)
    assert found == [] and executed["TLS-ATK-001"] == "ran"


def test_target_uses_a_verified_public_address(monkeypatch):
    class FakeDoh:
        answers = {"A": ["93.184.216.34"], "AAAA": []}

        def _query(self, name, rtype):
            return self.answers[rtype]

    monkeypatch.setattr(sslchecks, "DohResolver", FakeDoh)
    assert sslchecks._target(make_snap()) == TARGET
    FakeDoh.answers = {"A": ["93.184.216.34", "10.0.0.1"], "AAAA": []}
    with pytest.raises(CheckSkipped):
        sslchecks._target(make_snap())
    FakeDoh.answers = {"A": [], "AAAA": []}
    with pytest.raises(CheckSkipped):
        sslchecks._target(make_snap())


REQ = "sslyze==6.0.0 \\\n    --hash=sha256:" + "a" * 64 + "\n"


@pytest.fixture
def fake_pip(env, monkeypatch):
    state = {"text": json.dumps({"requirements": REQ})}

    def resource():
        if state["text"] is None:
            raise FileNotFoundError("pip-sslyze.json")
        return state["text"]

    def venv(python, target):
        (target / "Scripts").mkdir(parents=True)
        (target / "Scripts" / "python.exe").write_bytes(b"x")

    monkeypatch.setattr(piptools, "_resource_text", resource)
    monkeypatch.setattr(piptools, "_make_venv", venv)
    return state


def pip_runner(calls, code=0):
    def fake(args, *, cwd, timeout=None, root=None, extra_env=None):
        calls.append(([str(a) for a in args], (Path(cwd) / "requirements.txt").read_text("utf-8")))
        return ToolResult(code, "", "", False)
    return fake


def test_pip_install_is_hash_pinned_isolated_and_https_only(fake_pip, monkeypatch):
    calls: list = []
    monkeypatch.setattr(piptools, "run_tool", pip_runner(calls))
    assert manager.status(SSLYZE) == "missing"
    manager.install(SSLYZE)
    assert manager.status(SSLYZE) == "installed"
    args, requirements = calls[0]
    for flag in ("--require-hashes", "--no-deps", "--only-binary=:all:", "--no-binary=sslyze",
                 "https://pypi.org/simple"):
        assert flag in args
    assert "--hash=sha256:" in requirements
    assert manager.component_checker(lock=[SSLYZE])("sslyze") is True
    fake_pip["text"] = json.dumps({"requirements": REQ.replace("6.0.0", "6.0.1")})
    assert manager.status(SSLYZE) == "outdated"
    assert list(paths.cache_dir().glob("tmp*")) == []


def test_pip_install_refuses_unpinned_and_cleans_up_after_failure(fake_pip, monkeypatch):
    calls: list = []
    monkeypatch.setattr(piptools, "run_tool", pip_runner(calls, code=1))
    with pytest.raises(ClaudiosError) as e:
        manager.install(SSLYZE)
    assert e.value.code == E.TOOL_FAILED and not (paths.tools_dir() / "sslyze").exists()
    fake_pip["text"] = json.dumps({"requirements": "sslyze==6.0.0\n"})
    assert manager.status(SSLYZE) == "not_pinned"
    fake_pip["text"] = None
    with pytest.raises(ClaudiosError) as e:
        manager.install(SSLYZE)
    assert e.value.code == E.COMPONENT_NOT_PINNED and len(calls) == 1


def test_frozen_build_has_no_python_for_the_environment(fake_pip, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(ClaudiosError) as e:
        manager.install(SSLYZE)
    assert e.value.code == E.COMPONENT_MISSING


def test_sslyze_is_part_of_the_lock_before_npm_tools():
    names = [c.name for c in load_lock()]
    assert "sslyze" in names and names.index("sslyze") < names.index("npm-tools")
    assert SSLYZE.kind == "pip" and not SSLYZE.url and not SSLYZE.sha256
