import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location("check_files", ROOT / "tools" / "check_files.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_python_files_lie_outside_the_package():
    assert load_module().stray_files() == []


def test_every_package_folder_has_an_init_file():
    assert load_module().folders_without_init() == []


def test_every_import_of_the_package_points_to_an_existing_module():
    assert load_module().unresolved_imports() == []


def test_the_checker_finds_stray_files_missing_init_files_and_broken_imports(tmp_path):
    module = load_module()
    pkg = tmp_path / "src" / "claudios"
    (pkg / "core").mkdir(parents=True)
    (pkg / "ui").mkdir()
    (tmp_path / "tests").mkdir()
    (pkg / "__init__.py").write_text('USER_AGENT = "x"\n', "utf-8")
    (pkg / "core" / "__init__.py").write_text("", "utf-8")
    (pkg / "core" / "other.py").write_text("thing = 1\n", "utf-8")
    (pkg / "core" / "good.py").write_text(
        "from .. import USER_AGENT\nfrom . import other\nfrom .other import thing\n", "utf-8")
    (pkg / "core" / "bad.py").write_text(
        "from .missing import x\nfrom .. import nothere\nimport claudios.core.ghost\n", "utf-8")
    (pkg / "ui" / "page.py").write_text("value = 1\n", "utf-8")
    (tmp_path / "src" / "limits.py").write_text("old = 1\n", "utf-8")
    (tmp_path / "tests" / "test_x.py").write_text(
        "from claudios.core import other\nfrom claudios.core import ghost2\n", "utf-8")
    assert module.stray_files(tmp_path) == ["src/limits.py"]
    assert module.folders_without_init(tmp_path) == ["src/claudios/ui"]
    joined = "\n".join(module.unresolved_imports(tmp_path))
    for expected in ("bad.py:1", "bad.py:2", "bad.py:3", "test_x.py:2"):
        assert expected in joined
    assert "good.py" not in joined and "test_x.py:1" not in joined


def test_the_checker_reports_missing_required_files_in_an_empty_project(tmp_path):
    total, found = load_module().collect(tmp_path)
    assert total > 100 and any(title.startswith("Datei fehlt") for _level, title, _msg in found)
