import json

import pytest

from claudios import paths
from claudios.checks import npmchecks


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def write_package(content):
    folder = paths.tools_dir() / "npm-tools" / "node_modules" / "retire"
    folder.mkdir(parents=True)
    (folder / "package.json").write_text(json.dumps(content), "utf-8")


def test_retire_entry_point_comes_from_its_package_json(env):
    write_package({"bin": {"retire": "./lib/cli.js"}})
    assert npmchecks._retire_rel() == "node_modules/retire/lib/cli.js"


def test_retire_entry_point_as_plain_string(env):
    write_package({"bin": "bin/retire.js"})
    assert npmchecks._retire_rel() == "node_modules/retire/bin/retire.js"


@pytest.mark.parametrize("bad", [{"bin": "../../evil.js"}, {"bin": "/etc/x"}, {"bin": {"other": "x.js"}}, {}])
def test_unsafe_or_missing_entry_points_fall_back(env, bad):
    write_package(bad)
    assert npmchecks._retire_rel() == npmchecks._RETIRE_FALLBACK


def test_without_the_package_the_fallback_is_used(env):
    assert npmchecks._retire_rel() == npmchecks._RETIRE_FALLBACK
