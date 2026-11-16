import hashlib
import io
import stat
import zipfile

import httpx
import pytest

from claudios import paths
from claudios.components import manager
from claudios.components.lock import Component, load_lock, parse_lock
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.registry import REGISTRY, check
from claudios.i18n.strings import TEXTS


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def comp(name="java", data=b"", url="https://example.test/jre.zip", **kw):
    values = dict(name=name, title=name.upper(), kind="archive", version="1.0", url=url,
                  sha256=hashlib.sha256(data).hexdigest(), size=len(data), license="MIT",
                  source="https://example.test", depends=(), exe="**/bin/java.exe", filename="", strip_top=True)
    values.update(kw)
    return Component(**values)


def client_for(data: bytes, status: int = 200, calls: list | None = None):
    def handler(request):
        if calls is not None:
            calls.append(str(request.url))
        return httpx.Response(status, content=data)
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(paths, "reports_dir", lambda: tmp_path / "reports")
    return tmp_path


def test_install_verifies_hash_extracts_and_strips_top_folder(env):
    data = zip_bytes({"jdk-21/bin/java.exe": b"x", "jdk-21/lib/a.txt": b"y"})
    c = comp(data=data)
    phases = []
    manager.install(c, client=client_for(data), progress=lambda name, phase, d, t: phases.append(phase))
    assert manager.status(c) == "installed"
    assert (paths.tools_dir() / "java" / "bin" / "java.exe").is_file()
    assert {"download", "verify", "extract"} <= set(phases)
    assert manager.component_checker(lock=[c])("java") is True
    assert manager.tool_path("java", lock=[c]).name == "java.exe"
    assert list(paths.cache_dir().iterdir()) == []


def test_wrong_checksum_is_rejected_and_nothing_is_installed(env):
    data = zip_bytes({"d/bin/java.exe": b"x"})
    bad = comp(data=data, sha256="0" * 64)
    with pytest.raises(ClaudiosError) as e:
        manager.install(bad, client=client_for(data))
    assert e.value.code == E.CHECKSUM_MISMATCH
    assert not (paths.tools_dir() / "java").exists() and manager.status(bad) == "missing"
    assert list(paths.cache_dir().iterdir()) == []


def test_component_without_checksum_is_never_downloaded(env):
    calls: list = []
    unpinned = comp(sha256="")
    assert manager.status(unpinned) == "not_pinned"
    with pytest.raises(ClaudiosError) as e:
        manager.install(unpinned, client=client_for(b"", calls=calls))
    assert e.value.code == E.COMPONENT_NOT_PINNED and calls == []


def test_downloads_follow_https_redirects_but_never_downgrade(env):
    data = zip_bytes({"d/bin/java.exe": b"x"})
    c = comp(data=data)

    def good(request):
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"location": "https://cdn.test/f.zip"})
        return httpx.Response(200, content=data)

    manager.install(c, client=httpx.Client(transport=httpx.MockTransport(good)))
    assert manager.status(c) == "installed"

    insecure = "http" + "://evil.test/x.zip"
    bad_client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": insecure})))
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=data, version="2.0"), client=bad_client)
    assert e.value.code == E.DOWNLOAD_FAILED


def test_http_error_and_size_limit_are_download_failures(env, monkeypatch):
    data = zip_bytes({"d/bin/java.exe": b"x"})
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=data), client=client_for(b"", status=404))
    assert e.value.code == E.DOWNLOAD_FAILED
    monkeypatch.setattr(manager, "MAX_DOWNLOAD", 10)
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=data), client=client_for(data))
    assert e.value.code == E.DOWNLOAD_FAILED


@pytest.mark.parametrize("name", ["../evil.txt", "a/../../evil.txt", "C:/evil.txt"])
def test_zip_slip_is_blocked(env, name):
    data = zip_bytes({"a/bin/java.exe": b"x", name: b"boom"})
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=data), client=client_for(data))
    assert e.value.code == E.UNSAFE_ARCHIVE
    assert not (paths.tools_dir() / "java").exists()
    assert not (paths.data_dir() / "evil.txt").exists() and not (env / "evil.txt").exists()


def test_symlink_and_corrupt_archives_and_missing_exe_are_rejected(env):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        info = zipfile.ZipInfo("a/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "target")
    link = buf.getvalue()
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=link), client=client_for(link))
    assert e.value.code == E.UNSAFE_ARCHIVE
    junk = b"this is not a zip"
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=junk), client=client_for(junk))
    assert e.value.code == E.UNSAFE_ARCHIVE
    no_exe = zip_bytes({"d/readme.txt": b"x"})
    with pytest.raises(ClaudiosError) as e:
        manager.install(comp(data=no_exe), client=client_for(no_exe))
    assert e.value.code == E.TOOL_FAILED
    assert not (paths.tools_dir() / "java").exists()


def test_single_file_component_and_outdated_detection(env):
    data = b"jar-bytes"
    c = comp(name="css-validator", data=data, kind="file", filename="css-validator.jar",
             exe="css-validator.jar", strip_top=False)
    manager.install(c, client=client_for(data))
    assert (paths.tools_dir() / "css-validator" / "css-validator.jar").read_bytes() == data
    assert manager.status(c) == "installed"
    newer = comp(name="css-validator", data=b"other", kind="file", filename="css-validator.jar",
                 exe="css-validator.jar", strip_top=False, version="2.0")
    assert manager.status(newer) == "outdated"


def test_shipped_lock_is_valid_and_ordered():
    lock = load_lock()
    names = [c.name for c in lock]
    assert names == ["java", "node", "vnu", "css-validator", "zap"]
    for c in lock:
        assert all(dep in names[: names.index(c.name)] for dep in c.depends)
        assert c.url == "" or c.url.startswith("https://")


def test_parse_lock_rejects_bad_entries():
    base = {"name": "x", "title": "X", "kind": "archive", "license": "MIT", "source": "https://x.test",
            "exe": "x.exe"}
    assert parse_lock({"schema": 1, "components": [base]})[0].name == "x"
    for bad in ({**base, "url": "http" + "://x.test/a.zip"}, {**base, "sha256": "zz", "url": "https://x.test/a"},
                {**base, "depends": ["nope"]}, {**base, "kind": "exe"}, {**base, "name": "Bad Name"},
                {**base, "kind": "file", "filename": "../a.jar"}, {**base, "sha256": "a" * 64}):
        with pytest.raises(ValueError):
            parse_lock({"schema": 1, "components": [bad]})
    with pytest.raises(ValueError):
        parse_lock({"schema": 2, "components": []})


def _populate(env):
    for name in ("java", "vnu"):
        folder = paths.tools_dir() / name
        folder.mkdir()
        (folder / "f.bin").write_bytes(b"x" * 10)
    (paths.cache_dir() / "c.tmp").write_bytes(b"x")
    (paths.logs_dir() / "claudios.log").write_text("l")
    (paths.logs_dir() / "audit.jsonl").write_text("a")
    (paths.config_dir() / "settings.json").write_text("{}")
    reports = paths.reports_dir()
    reports.mkdir(parents=True)
    (reports / "r.zip").write_bytes(b"z")


def test_uninstall_removes_only_selected_and_keeps_audit_log(env):
    lock = [comp(), comp(name="vnu", depends=("java",), exe="**/vnu.jar")]
    _populate(env)
    items = {i.key: i for i in manager.uninstall_items(lock)}
    assert set(items) == {"tool:java", "tool:vnu", "cache", "logs", "config", "reports"}
    assert items["reports"].default is False and items["config"].default is False
    assert items["tool:java"].default is True and items["tool:java"].size == 10
    assert manager.dependents(["java"], lock) == ["vnu"]
    result = manager.uninstall(["tool:java", "cache", "logs"], lock)
    assert result == {"tool:java": None, "cache": None, "logs": None}
    tools, logs = paths.tools_dir(), paths.logs_dir()
    assert not (tools / "java").exists() and (tools / "vnu").exists()
    assert (logs / "audit.jsonl").exists() and not (logs / "claudios.log").exists()
    assert (paths.config_dir() / "settings.json").exists() and (paths.reports_dir() / "r.zip").exists()


def test_uninstall_ignores_unknown_and_unsafe_keys(env):
    lock = [comp()]
    _populate(env)
    result = manager.uninstall(["tool:../../x", "bogus", "tool:vnu"], lock)
    assert result == {"tool:../../x": "unknown", "bogus": "unknown", "tool:vnu": "unknown"}
    assert (paths.tools_dir() / "java").exists() and (paths.tools_dir() / "vnu").exists()
    everything = manager.uninstall(["config", "reports"], lock)
    assert everything == {"config": None, "reports": None}
    assert not paths.reports_dir().exists()


def test_affected_checks_counts_checks_that_need_removed_tools(env):
    lock = [comp(), comp(name="vnu", depends=("java",), exe="**/vnu.jar")]
    before_java = manager.affected_checks(["java"], lock)
    before_vnu = manager.affected_checks(["vnu"], lock)

    @check("TST-NDS-001", title="T ## T", why="w ## w", method="m ## m", logic="l ## l", fix="f ## f",
           refs=["https://example.com/"], needs=("vnu",))
    def _needs_vnu(snap):
        return []

    try:
        assert manager.affected_checks(["java"], lock) == before_java + 1
        assert manager.affected_checks(["vnu"], lock) == before_vnu + 1
    finally:
        REGISTRY.pop("TST-NDS-001")


def test_component_texts_exist_in_both_languages():
    keys = ["nav.components", "cmp.st.installed", "cmp.st.missing", "cmp.st.outdated", "cmp.st.not_pinned",
            "cmp.phase.download", "cmp.phase.verify", "cmp.phase.extract", "unin.item.cache", "unin.item.logs",
            "unin.item.config", "unin.item.reports"]
    for lang in ("de", "en"):
        for key in keys:
            assert TEXTS[lang][key].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
