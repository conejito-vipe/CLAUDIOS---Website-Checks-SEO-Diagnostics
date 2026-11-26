"""macOS: Speicherort, Schlüsselbund (mit nachgebildeter Security.framework), Komponenten-Filter, Update ohne stillen Installer, Deinstallation."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from claudios import paths
from claudios.components import lock
from claudios.core.errors import ClaudiosError
from claudios.gsc import credstore
from claudios.ui import uninstall, update_check


def test_data_folder_follows_the_system(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(paths, "_normalized", True)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    assert paths.data_dir() == tmp_path / "Library" / "Application Support" / paths.APP_FOLDER
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.data_dir() == tmp_path / "local" / paths.APP_FOLDER
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("LOCALAPPDATA")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths.data_dir() == tmp_path / "xdg" / paths.APP_FOLDER


def test_the_mac_offers_only_components_that_are_marked_for_it(monkeypatch):
    monkeypatch.delenv("CLAUDIOS_PLATFORM")
    monkeypatch.setattr(lock.sys, "platform", "linux")
    assert lock.host_platform() == "windows" and len(lock.load_lock()) >= 9
    monkeypatch.setattr(lock.sys, "platform", "darwin")
    assert lock.host_platform() == "macos"
    assert all("macos" in c.platforms for c in lock.load_lock())


def test_unknown_platform_names_in_the_lock_are_refused():
    raw = {"schema": 1, "components": [{"name": "x", "title": "x", "kind": "file", "url": "https://e.com/x", "filename": "x",
                                         "license": "l", "source": "s", "exe": "x", "platforms": ["amiga"]}]}
    with pytest.raises(ValueError, match="platforms"):
        lock.parse_lock(raw)
    raw["components"][0]["platforms"] = ["windows", "macos"]
    assert lock.parse_lock(raw)[0].platforms == ("windows", "macos")


class FakeSecurity:
    """Nachbildung der fünf Funktionen aus Security.framework, die der Schlüsselbund-Speicher nutzt."""

    def __init__(self):
        self.items, self.released, self.fail = {}, 0, {}
        self.SecKeychainAddGenericPassword = self._add
        self.SecKeychainFindGenericPassword = self._find
        self.SecKeychainItemModifyAttributesAndData = self._modify
        self.SecKeychainItemFreeContent = lambda _a, _b: 0
        self.SecKeychainItemDelete = self._delete
        self.CFRelease = self._release

    def _add(self, _kc, _sl, service, _al, account, plen, password, _item):
        if self.fail.get("add"):
            return self.fail["add"]
        key = (service, account)
        if key in self.items:
            return credstore.ERR_SEC_DUPLICATE
        self.items[key] = password
        return 0

    def _find(self, _kc, _sl, service, _al, account, length, data, item):
        key = (service, account)
        if self.fail.get("find"):
            return self.fail["find"]
        if key not in self.items:
            return credstore.ERR_SEC_NOT_FOUND
        self._last = key
        return 0

    def _modify(self, item, _attrs, _len, password):
        self.items[self._last] = password
        return self.fail.get("modify", 0)

    def _delete(self, item):
        self.items.pop(self._last, None)
        return self.fail.get("delete", 0)

    def _release(self, _item):
        self.released += 1


class FakeCT:
    """Ersatz für ctypes, soweit der Speicher es braucht: Wert aus dem Eintrag statt aus einem Zeiger."""

    def __init__(self, sec):
        self.sec = sec
        import ctypes
        self.c_uint32, self.c_void_p, self.byref = ctypes.c_uint32, ctypes.c_void_p, ctypes.byref
        self.string_at = lambda _ptr, _n: sec.items[sec._last]


@pytest.fixture
def store():
    sec = FakeSecurity()
    st = credstore.MacStore(sec=sec, cf=sec)
    st._ct = FakeCT(sec)
    return st, sec


def test_keychain_roundtrip_overwrite_delete_and_missing_entries(store):
    st, sec = store
    assert st.read("gsc") is None
    st.write("gsc", "geheim-1")
    assert st.read("gsc") == "geheim-1"
    st.write("gsc", "geheim-2")  # vorhanden: ersetzt, nicht doppelt
    assert st.read("gsc") == "geheim-2" and len(sec.items) == 1
    st.delete("gsc")
    assert st.read("gsc") is None
    st.delete("gsc")  # fehlender Eintrag ist kein Fehler
    assert sec.released >= 3  # jeder Verweis wird freigegeben


def test_keychain_errors_are_reported_and_never_look_like_success(store):
    st, sec = store
    sec.fail["add"] = -1
    with pytest.raises(ClaudiosError):
        st.write("gsc", "x")
    sec.fail = {"find": -2}
    with pytest.raises(ClaudiosError):
        st.read("gsc")
    st.items = None
    sec.items[(b"CLAUDIOS", b"gsc")] = b"x"
    sec.fail = {}
    st2 = credstore.MacStore(sec=sec, cf=sec)
    st2._ct = FakeCT(sec)
    sec.fail["delete"] = -3
    with pytest.raises(ClaudiosError):
        st2.delete("gsc")
    sec.fail = {"find": -4}
    with pytest.raises(ClaudiosError):
        st2.delete("gsc")


def test_a_failing_modify_after_a_duplicate_is_reported(store):
    st, sec = store
    st.write("gsc", "a")
    sec.fail["modify"] = -9
    with pytest.raises(ClaudiosError):
        st.write("gsc", "b")


def test_the_secret_never_leaves_through_a_command_line():
    source = Path(credstore.__file__).read_text("utf-8")
    assert "subprocess" not in source and "/usr/bin/security" not in source


def test_get_store_uses_the_keychain_on_the_mac_and_memory_when_it_cannot_load(monkeypatch):
    monkeypatch.setattr(credstore.sys, "platform", "darwin")
    monkeypatch.setattr(credstore, "MacStore", lambda: "keychain")
    assert credstore.get_store() == "keychain"

    def broken():
        raise OSError("nicht da")

    monkeypatch.setattr(credstore, "MacStore", broken)
    assert credstore.get_store().persistent is False


def test_on_the_mac_an_update_opens_the_release_page_and_downloads_nothing(monkeypatch):
    opened = []
    monkeypatch.setattr(update_check.sys, "platform", "darwin")
    monkeypatch.setattr(update_check.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString())))
    monkeypatch.setattr(update_check, "UpdateDialog", lambda *a: (_ for _ in ()).throw(AssertionError("kein Download")))
    update_check.install_update(None, SimpleNamespace(page_url="https://github.com/x/y/releases/tag/v1.0.1"))
    assert opened == ["https://github.com/x/y/releases/tag/v1.0.1"]


def test_on_the_mac_the_manual_uninstall_hint_names_the_app_and_the_folder_is_the_mac_one(monkeypatch):
    from claudios.i18n.strings import TEXTS

    monkeypatch.setattr(uninstall.sys, "platform", "darwin")
    assert uninstall.display_folder().startswith("~/Library/Application Support")
    for lang in ("de", "en"):
        assert "CLAUDIOS.app" in TEXTS[lang]["app.uninstall.manual.mac"] and "{folder}" in TEXTS[lang]["app.uninstall.partial"]
    monkeypatch.setattr(uninstall.sys, "platform", "win32")
    assert "LOCALAPPDATA" in uninstall.display_folder()


def test_the_platform_can_be_forced_for_tests(monkeypatch):
    monkeypatch.setattr(lock.sys, "platform", "darwin")
    monkeypatch.setenv("CLAUDIOS_PLATFORM", "windows")
    assert lock.host_platform() == "windows"
    monkeypatch.setenv("CLAUDIOS_PLATFORM", "unsinn")  # ungültiger Wert wird ignoriert
    assert lock.host_platform() == "macos"
