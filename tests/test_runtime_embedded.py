import importlib.util
import json
from pathlib import Path

import pytest

from claudios.components import (
    _runtimelock,
    extra_pipwheel,
    extra_pythonruntime,
    extra_sslyze,
    manager,
    pipembedtools,
    piptools,
)
from claudios.components.lock import load_lock
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.toolrunner import ToolResult

GOOD = {"python": {"version": "3.12.10", "url": "https://example.test/py.zip", "sha256": "a" * 64, "size": 10},
        "pip": {"version": "25.0", "url": "https://example.test/pip.whl", "sha256": "B" * 64, "size": 5}}
PIN = {"url": "https://example.test/sslyze-6.3.1-py3-none-any.whl", "sha256": "c" * 64,
       "filename": "sslyze-6.3.1-py3-none-any.whl", "size": 5, "version": "6.3.1"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def test_only_complete_https_entries_with_a_valid_checksum_are_accepted():
    assert _runtimelock.parse_entry(GOOD, "python")["sha256"] == "a" * 64
    assert _runtimelock.parse_entry(GOOD, "pip")["sha256"] == "b" * 64  # klein geschrieben
    for bad in (None, {}, {"python": {}}, {"python": {**GOOD["python"], "sha256": "xyz"}},
                {"python": {**GOOD["python"], "url": "http" + "://example.test/x"}},
                {"python": {**GOOD["python"], "size": 0}}):
        assert _runtimelock.parse_entry(bad, "python") == {}


def test_the_runtime_components_exist_only_in_the_built_program(monkeypatch):
    assert extra_pythonruntime.build(False) is None and extra_pipwheel.build(False) is None
    assert {"python-runtime", "pip-wheel"}.isdisjoint(c.name for c in load_lock())
    monkeypatch.setattr(extra_pythonruntime, "entry", lambda key: _runtimelock.parse_entry(GOOD, key))
    monkeypatch.setattr(extra_pipwheel, "entry", lambda key: _runtimelock.parse_entry(GOOD, key))
    runtime, wheel = extra_pythonruntime.build(True), extra_pipwheel.build(True)
    assert runtime.kind == "archive" and runtime.sha256 == "a" * 64 and runtime.exe == "python.exe"
    assert wheel.kind == "file" and wheel.filename == "pip.whl" and wheel.sha256 == "b" * 64
    monkeypatch.setattr(extra_pythonruntime, "entry", lambda key: {})
    assert extra_pythonruntime.build(True).sha256 == ""  # ohne Sperrdatei: nie installierbar


def test_sslyze_uses_a_venv_with_python_and_the_embedded_runtime_in_the_built_program():
    normal, built = extra_sslyze.build(False), extra_sslyze.build(True)
    assert (normal.kind, normal.exe, normal.depends) == ("pip", "Scripts/python.exe", ())
    assert (built.kind, built.exe) == ("pipembed", "python.exe")
    assert built.depends == ("python-runtime", "pip-wheel")
    assert extra_sslyze.COMPONENT.kind == "pip"
    assert manager._handler("pipembed") is pipembedtools and pipembedtools.status is piptools.status


def _runtime(folder: Path) -> Path:
    folder.mkdir(parents=True)
    (folder / "python.exe").write_bytes(b"exe")
    (folder / "python312._pth").write_text("python312.zip\n.\n\n# Uncomment to run site.main()\n#import site\n", "utf-8")
    return folder


def test_prepare_runtime_enables_site_packages_and_the_pip_wheel(env):
    wheel = env / "pip.whl"
    wheel.write_bytes(b"wheel")
    python = pipembedtools.prepare_runtime(_runtime(env / "src"), env / "target", wheel)
    lines = (env / "target" / "python312._pth").read_text("utf-8").splitlines()
    assert python == env / "target" / "python.exe" and (env / "target" / "pip.whl").is_file()
    assert lines[-3:] == ["pip.whl", "Lib\\site-packages", "import site"] and "#import site" not in lines
    assert (env / "target" / "Lib" / "site-packages").is_dir()
    with pytest.raises(ClaudiosError) as error:
        pipembedtools.prepare_runtime(env / "nothing", env / "target2", wheel)
    assert error.value.code == E.COMPONENT_MISSING


def _tools(root: Path, monkeypatch):
    _runtime(root / "python-runtime")
    (root / "pip-wheel").mkdir(parents=True)
    (root / "pip-wheel" / "pip.whl").write_bytes(b"wheel")
    found = {"python-runtime": root / "python-runtime" / "python.exe", "pip-wheel": root / "pip-wheel" / "pip.whl"}
    monkeypatch.setattr(pipembedtools, "_tool", found.get)


def test_install_runs_pip_with_hashes_into_the_copy_and_writes_the_marker(env, monkeypatch):
    """Alter Weg (Bau aus dem Quellarchiv), wenn es kein festes Wheel gibt."""
    root = env / "tools"
    _tools(root, monkeypatch)
    monkeypatch.setattr(pipembedtools.sslyzewheel, "load_pin", lambda: {})
    calls = []

    def fake(args, **kwargs):
        calls.append(([str(a) for a in args], kwargs, Path(args[-1]).read_text("utf-8")))
        return ToolResult(0, "", "", False)

    monkeypatch.setattr(pipembedtools, "run_tool", fake)
    comp = extra_sslyze.build(True)
    pipembedtools.install(comp, root=root)
    args, kwargs, requirements = calls[0]
    assert args[0].endswith("python.exe") and args[1:4] == ["-m", "pip", "install"]
    assert "--require-hashes" in args and "--no-deps" in args and "--no-binary=sslyze" in args and "--target" in args
    assert "--hash=sha256:" in requirements and kwargs["root"] == root
    marker = json.loads((root / "sslyze" / piptools.MARKER).read_text("utf-8"))
    assert marker["sha256"] == piptools.lock_hash() and pipembedtools.status(comp, root) == "installed"


def test_a_failed_install_leaves_nothing_behind_and_a_missing_runtime_is_reported(env, monkeypatch):
    root = env / "tools"
    _tools(root, monkeypatch)
    monkeypatch.setattr(pipembedtools.sslyzewheel, "load_pin", lambda: {})
    monkeypatch.setattr(pipembedtools, "run_tool", lambda args, **kwargs: ToolResult(1, "", "", False))
    comp = extra_sslyze.build(True)
    with pytest.raises(ClaudiosError) as error:
        pipembedtools.install(comp, root=root)
    assert error.value.code == E.TOOL_FAILED and not (root / "sslyze").exists()
    monkeypatch.setattr(pipembedtools, "_tool", lambda name: None)
    with pytest.raises(ClaudiosError) as error:
        pipembedtools.install(comp, root=root)
    assert error.value.code == E.COMPONENT_MISSING


def _pinned(env, monkeypatch, fail_on=None):
    """Wheel-Weg mit gefälschtem Download und gefälschten Prozessen (kein Netz). Gibt Downloads und Aufrufe zurück."""
    root = env / "tools"
    _tools(root, monkeypatch)
    monkeypatch.setattr(pipembedtools.sslyzewheel, "load_pin", lambda: PIN)
    downloads, calls = [], []

    def fake_download(comp, dest, **kwargs):
        downloads.append((comp.url, comp.sha256))
        dest.write_bytes(b"wheel")

    def fake(args, **kwargs):
        last = str(args[-1])
        text = Path(args[-1]).read_text("utf-8") if last.endswith("requirements.txt") else ""
        calls.append(([str(a) for a in args], text))
        code = 1 if fail_on and fail_on in [str(a) for a in args] else 0
        return ToolResult(code, "", "", False)

    monkeypatch.setattr(manager, "download", fake_download)
    monkeypatch.setattr(pipembedtools, "run_tool", fake)
    return root, downloads, calls


def test_a_pinned_wheel_is_checked_installed_without_building_and_imported(env, monkeypatch):
    root, downloads, calls = _pinned(env, monkeypatch)
    comp = extra_sslyze.build(True)
    pipembedtools.install(comp, root=root)
    assert downloads == [(PIN["url"], PIN["sha256"])]
    assert len(calls) == 3
    deps, text = calls[0]
    assert "--require-hashes" in deps and "--no-deps" in deps and "--no-binary=sslyze" not in deps
    assert "sslyze==" not in text and "nassl==" in text and "--hash=sha256:" in text
    wheel_call, _ = calls[1]
    assert "--no-index" in wheel_call and "--no-deps" in wheel_call and wheel_call[-1].endswith(PIN["filename"])
    assert calls[2][0][-2:] == ["-c", "import sslyze"]
    assert pipembedtools.status(comp, root) == "installed"


def test_a_wheel_that_cannot_be_imported_counts_as_failed_and_leaves_nothing(env, monkeypatch):
    root, _downloads, calls = _pinned(env, monkeypatch, fail_on="import sslyze")
    comp = extra_sslyze.build(True)
    with pytest.raises(ClaudiosError) as error:
        pipembedtools.install(comp, root=root)
    assert error.value.code == E.TOOL_FAILED and not (root / "sslyze").exists()
    assert len(calls) == 3


def test_the_lock_script_picks_only_the_universal_wheel():
    path = Path(__file__).resolve().parent.parent / "tools" / "make_runtime_lock.py"
    spec = importlib.util.spec_from_file_location("make_runtime_lock", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    wheel = {"packagetype": "bdist_wheel", "filename": "pip-25.0-py3-none-any.whl",
             "url": "https://files.example/pip.whl", "digests": {"sha256": "a" * 64}}
    sdist = {"packagetype": "sdist", "filename": "pip-25.0.tar.gz", "url": "https://files.example/pip.tgz",
             "digests": {"sha256": "c" * 64}}
    assert module.choose_wheel({"urls": [sdist, wheel]}) == wheel
    assert module.choose_wheel({"urls": [sdist]}) is None and module.choose_wheel({}) is None
