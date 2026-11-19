import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mirror, lock = load("mirror_vnu"), load("update_lock")


def test_the_sha1_list_of_the_vendor_is_read_defensively():
    assert mirror.listed_sha1("a" * 40 + "  vnu.jar\n") == "a" * 40
    for junk in ("", "   ", "xyz  vnu.jar", "A" * 39):
        assert mirror.listed_sha1(junk) == ""


def test_the_version_is_taken_from_the_tool_output():
    assert mirror.parse_version("26.1.3\n") == "26.1.3" and mirror.parse_version("keine Zahl") == ""


def test_only_a_real_jar_with_a_main_class_is_accepted(tmp_path):
    good, bad = tmp_path / "good.jar", tmp_path / "bad.jar"
    with zipfile.ZipFile(good, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: x.Main\n")
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("a.txt", "x")
    plain = tmp_path / "plain.jar"
    plain.write_bytes(b"not a zip")
    assert mirror.has_main_class(good) and not mirror.has_main_class(bad) and not mirror.has_main_class(plain)


def test_the_lock_entry_is_replaced_and_marked_as_pinned():
    raw = {"components": [{"name": "java"}, {"name": "vnu", "version": "latest", "resolver": {"type": "github"}}]}
    assert mirror.update_entry(raw, version="1.2.3", url="https://example.test/vnu.jar", sha256="a" * 64, size=5)
    entry = raw["components"][1]
    assert entry["sha256"] == "a" * 64 and entry["resolver"] == {"type": "pinned"} and entry["version"] == "1.2.3"
    assert not mirror.update_entry({"components": []}, version="x", url="u", sha256="b", size=1)


def test_the_lock_updater_leaves_pinned_entries_alone():
    assert lock.is_pinned({"resolver": {"type": "pinned"}})
    assert not lock.is_pinned({"resolver": {"type": "github"}}) and not lock.is_pinned({})
