"""Bildschirmfotos: nur erlaubte Dateinamen und Größen, keine Pfadtricks, Aufräumen bei jedem Fehler, Begrenzung der Anzahl."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from claudios.core import probe_shots
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.limits import LIMITS


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(probe_shots.paths, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(probe_shots.paths, "tools_dir", lambda: tmp_path / "tools")
    (tmp_path / "cache").mkdir()
    monkeypatch.setattr(probe_shots, "_node", lambda: "/n/node")
    monkeypatch.setattr(probe_shots, "_pin", lambda _s: "93.184.216.34")
    monkeypatch.setattr(probe_shots, "_environment", lambda _n: {})
    return tmp_path


def snap(url="https://example.com/", status=200, host="Example.COM"):
    page = SimpleNamespace(url=url, status=status)
    return SimpleNamespace(docs=lambda: [page], target=SimpleNamespace(host=host, registrable="example.com"))


def fake_tool(shots, files=None, content=None):
    """Ersetzt das Node-Skript: schreibt die Dateien in das übergebene Ausgabeverzeichnis und das Ergebnis."""
    def run(cmd, **_kw):
        source = json.loads(Path(cmd[2]).read_text("utf-8"))
        for name, size in (files or {}).items():
            target = Path(source["outdir"]) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"x" * size)
        Path(cmd[3]).write_text(content if content is not None else json.dumps({"shots": shots}), "utf-8")
    return run


def test_host_names_become_safe_folder_names():
    assert probe_shots._stem("Ex/../ample.COM:8080") == "ex-..-ample.com-8080" and probe_shots._stem("") == "site"
    assert len(probe_shots._stem("a" * 200)) == 60 and "/" not in probe_shots._stem("../../etc")


def test_only_https_pages_with_status_200_are_photographed(env):
    for s in (snap("http://example.com/"), snap(status=404)):
        assert probe_shots._run(s) == {"enabled": True, "skip": "no_pages"}


def test_missing_tools_or_a_failed_pin_are_a_skip(env, monkeypatch):
    monkeypatch.setattr(probe_shots, "_node", lambda: None)
    assert probe_shots._run(snap())["skip"] == "tool_not_found"
    monkeypatch.setattr(probe_shots, "_node", lambda: "/n/node")

    def pin_fails(_s):
        raise probe_shots._Skip("target_private")

    monkeypatch.setattr(probe_shots, "_pin", pin_fails)
    assert probe_shots._run(snap())["skip"] == "target_private"


def test_allowed_files_are_reported_and_the_folder_stays(env, monkeypatch):
    monkeypatch.setattr(probe_shots, "run_tool", fake_tool([{"file": "desktop.png"}, {"file": "mobile.png"}],
                                                           {"desktop.png": 100, "mobile.png": 50}))
    out = probe_shots._run(snap())
    assert out["skip"] is None and out["files"] == ["desktop.png", "mobile.png"] and Path(out["dir"]).is_dir()
    assert Path(out["dir"]).name.endswith("_example.com")


@pytest.mark.parametrize("name", ["../../evil.png", "/etc/passwd", "desktop.png/../x", "other.png", "desktop.PNG", "", None, 5])
def test_names_outside_the_whitelist_are_never_reported(env, monkeypatch, name):
    monkeypatch.setattr(probe_shots, "run_tool", fake_tool([{"file": name}], {"other.png": 10, "desktop.PNG": 10}))
    out = probe_shots._run(snap())
    assert out["skip"] == "shots_failed" and "files" not in out
    assert list((env / "cache" / "shots").iterdir()) == []  # leerer Ordner wird entfernt


def test_empty_and_oversized_files_are_dropped(env, monkeypatch):
    monkeypatch.setattr(probe_shots, "run_tool", fake_tool([{"file": "desktop.png"}, {"file": "mobile.png"}],
                                                           {"desktop.png": 0, "mobile.png": LIMITS.shot_bytes_max + 1}))
    assert probe_shots._run(snap())["skip"] == "shots_failed"
    monkeypatch.setattr(probe_shots, "run_tool", fake_tool([{"file": "mobile.png"}], {"mobile.png": LIMITS.shot_bytes_max}))
    assert probe_shots._run(snap())["files"] == ["mobile.png"]  # genau am Limit ist erlaubt


@pytest.mark.parametrize("content", ["kein json", "[]", '{"shots": "x"}', '{"shots": [5, null]}'])
def test_garbage_from_the_script_means_no_photos_and_no_leftovers(env, monkeypatch, content):
    monkeypatch.setattr(probe_shots, "run_tool", fake_tool(None, content=content))
    out = probe_shots._run(snap())
    assert out["skip"] in {"tool_output_unreadable", "shots_failed"}
    assert list((env / "cache" / "shots").iterdir()) == []


def test_a_failing_script_removes_the_output_folder(env, monkeypatch):
    monkeypatch.setattr(probe_shots, "run_tool", lambda *a, **k: (_ for _ in ()).throw(ClaudiosError(E.TOOL_FAILED)))
    assert probe_shots._run(snap())["skip"] == "tool_failed"
    assert list((env / "cache" / "shots").iterdir()) == []


def test_only_the_newest_folders_are_kept(env, monkeypatch):
    root = env / "cache" / "shots"
    root.mkdir()
    total = LIMITS.shots_keep + 3
    for i in range(total):
        (root / f"2026010{i}T000000_x").mkdir()
    probe_shots._prune(root)
    left = sorted(p.name for p in root.iterdir())
    assert len(left) == LIMITS.shots_keep and left[-1].startswith(f"2026010{total - 1}")


def test_the_environment_points_only_into_the_tools_folder(env, monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(probe_shots.paths, "tools_dir", lambda: env / "tools")
    monkeypatch.setattr(probe_shots, "node_env", lambda _p: {})
    out = probe_shots._environment("/n/node")
    assert out["NODE_PATH"].startswith(str(env / "tools")) and out["PLAYWRIGHT_BROWSERS_PATH"].startswith(str(env / "tools"))


async def test_collect_respects_the_switch_localhost_and_a_changed_dns(env, monkeypatch):
    s = snap()
    s.target.loopback = False
    monkeypatch.setattr(probe_shots.options, "enabled", lambda _n: False)
    assert (await probe_shots.collect(None, s, None))["skip"] == "shots_disabled"
    monkeypatch.setattr(probe_shots.options, "enabled", lambda _n: True)
    s.target.loopback = True
    assert (await probe_shots.collect(None, s, None))["skip"] == "localhost"
    s.target.loopback = False
    answers = iter([False])

    async def unchanged(_gk):
        return next(answers, True)

    monkeypatch.setattr(probe_shots, "_unchanged", unchanged)
    assert (await probe_shots.collect(None, s, None))["skip"] == "dns_changed"
    kept = env / "bilder"
    kept.mkdir()
    (kept / "desktop.png").write_bytes(b"x")
    monkeypatch.setattr(probe_shots, "_run", lambda _s: {"enabled": True, "skip": None, "dir": str(kept)})
    answers = iter([True, False])  # nach dem Lauf hat sich das DNS geändert: die Bilder werden verworfen
    assert (await probe_shots.collect(None, s, None))["skip"] == "dns_changed"
    assert not kept.exists()  # auch von der Platte
    kept.mkdir()
    answers = iter([True, True])
    assert (await probe_shots.collect(None, s, None))["skip"] is None and kept.exists()
