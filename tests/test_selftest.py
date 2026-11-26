"""Selbsttest des gebauten Programms: Bericht, Exit-Code, geschwärzte Pfade, jede Prüfung einzeln, Anbindung an app.main."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from claudios import app, selftest


def test_all_checks_pass_on_a_healthy_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr("claudios.paths.data_dir", lambda: tmp_path / "data")
    report = selftest.run_checks()
    failed = [c for c in report["checks"] if not c["ok"]]
    assert report["ok"] and not failed, failed
    assert [c["name"] for c in report["checks"]] == [n for n, _f in selftest.CHECKS]


def test_a_failing_check_is_reported_with_its_reason_and_the_others_still_run():
    def boom():
        raise RuntimeError("Baustein fehlt")

    report = selftest.run_checks((("a", lambda: "gut"), ("b", boom), ("c", lambda: "auch gut")))
    assert report["ok"] is False and [c["ok"] for c in report["checks"]] == [True, False, True]
    assert report["checks"][1]["detail"] == "RuntimeError: Baustein fehlt"


def test_run_writes_the_report_and_returns_the_exit_code(tmp_path, monkeypatch, capsys):
    target = tmp_path / "bericht.json"
    monkeypatch.setattr(selftest, "CHECKS", (("x", lambda: "ok"),))
    monkeypatch.setattr(selftest, "run_checks", lambda: {"ok": True, "version": "1", "checks": [{"name": "x", "ok": True, "detail": "ok", "ms": 0}]})
    assert selftest.run(["prog", "--selftest", str(target)]) == 0
    assert json.loads(target.read_text("utf-8"))["ok"] is True and "OK   x: ok" in capsys.readouterr().out
    monkeypatch.setattr(selftest, "run_checks", lambda: {"ok": False, "version": "1", "checks": [{"name": "x", "ok": False, "detail": "kaputt", "ms": 0}]})
    assert selftest.run(["prog", "--selftest", str(target)]) == 1 and "FEHL x: kaputt" in capsys.readouterr().out


def test_an_unwritable_report_path_makes_the_selftest_fail_instead_of_crashing(tmp_path, monkeypatch):
    blocker = tmp_path / "datei"
    blocker.write_text("x", "utf-8")
    monkeypatch.setattr(selftest, "run_checks", lambda: {"ok": True, "version": "1", "checks": []})
    assert selftest.run(["prog", "--selftest", str(blocker / "unter" / "b.json")]) == 1


def test_the_report_path_comes_from_the_argument_then_the_environment_then_the_log_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(selftest.ENV_OUT, str(tmp_path / "env.json"))
    assert selftest.output_path(["p", "--selftest", "arg.json"]) == Path("arg.json")
    assert selftest.output_path(["p", "--selftest"]) == tmp_path / "env.json"
    assert selftest.output_path(["p", "--selftest", "--andere"]) == tmp_path / "env.json"
    monkeypatch.delenv(selftest.ENV_OUT)
    monkeypatch.setattr("claudios.paths.logs_dir", lambda: tmp_path / "logs")
    assert selftest.output_path(["p"]) == tmp_path / "logs" / "selftest.json"


def test_the_home_folder_never_appears_in_the_report(monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: Path("/home/geheimer-name")))
    assert "geheimer-name" not in selftest._mask("exe=/home/geheimer-name/AppData/x.exe") and "~" in selftest._mask("/home/geheimer-name/x")


def test_a_missing_resource_or_module_is_detected(monkeypatch):
    monkeypatch.setattr(selftest, "LOCK_FILES", ("gibt-es-nicht.json",))
    with pytest.raises(RuntimeError, match="gibt-es-nicht.json"):
        selftest.check_resources()
    monkeypatch.setattr(selftest.pkgutil, "walk_packages", lambda *a, **k: [])
    with pytest.raises(RuntimeError, match="nur 0 Module"):
        selftest.check_modules()


def test_a_broken_doh_or_registry_is_a_failure(monkeypatch):
    monkeypatch.setattr("claudios.core._frozen_imports.doh_status", lambda: (False, "httpx fehlt"))
    with pytest.raises(RuntimeError, match="httpx fehlt"):
        selftest.check_doh()
    monkeypatch.setattr("claudios.core.registry.validate_registry", lambda: ["doppelte ID"])
    with pytest.raises(RuntimeError, match="doppelte ID"):
        selftest.check_registry()


def test_main_runs_the_selftest_before_anything_else(monkeypatch):
    monkeypatch.setattr(app.sys, "argv", ["CLAUDIOS.exe", "--selftest"])
    monkeypatch.setattr(selftest, "run", lambda *a: 42)
    assert app.main() == 42  # kein Splash, keine Sperre, kein Hauptprogramm


def test_the_windows_workflow_runs_the_selftest_on_the_built_and_on_the_installed_program():
    text = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-windows.yml").read_text("utf-8")
    assert text.count("--selftest") >= 2 and "/VERYSILENT" in text and "unins000.exe" in text and "Statusberichte" in text
