"""Windows-Anmeldeinformationsspeicher: Logik gegen eine Attrappe von advapi32 (die echte DLL gibt es nur unter Windows)."""
from __future__ import annotations

import ctypes
import sys

import pytest

from claudios.core.errors import ClaudiosError
from claudios.gsc import credstore, session


class Func:
    """Wie eine ctypes-Funktion: argtypes und restype lassen sich setzen."""

    def __init__(self, fn):
        self.fn, self.argtypes, self.restype = fn, None, None

    def __call__(self, *args):
        return self.fn(*args)


class FakeAdvapi:
    """Legt Einträge wie der Credential Manager ab: Name -> (Typ, Persist, Benutzer, Bytes)."""

    def __init__(self, *_a, **_k):
        self.items, self.keep, self.fail_write, self.delete_error = {}, [], False, 1168
        self.CredWriteW, self.CredReadW = Func(self._write), Func(self._read)
        self.CredFree, self.CredDeleteW = Func(lambda _ptr: None), Func(self._delete)

    def _write(self, ref, _flags):
        if self.fail_write:
            return 0
        cred = ref._obj
        raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        self.items[cred.TargetName] = (cred.Type, cred.Persist, cred.UserName, raw)
        return 1

    def _read(self, name, kind, _flags, out):
        if name not in self.items or kind != 1:
            return 0
        _t, _p, _u, raw = self.items[name]
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        cred = self.cred_type()
        cred.CredentialBlobSize = len(raw)
        cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        self.keep += [blob, cred]
        pointer = ctypes.pointer(cred)
        ctypes.memmove(ctypes.addressof(out._obj), ctypes.addressof(pointer), ctypes.sizeof(ctypes.c_void_p))
        self.keep.append(pointer)
        return 1

    def _delete(self, name, _kind, _flags):
        if name in self.items:
            del self.items[name]
            return 1
        self.last_error = self.delete_error
        return 0


@pytest.fixture
def store(monkeypatch):
    adv = FakeAdvapi()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: adv, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: getattr(adv, "last_error", 0), raising=False)  # nur Windows
    win = credstore.WindowsStore()
    adv.cred_type = win._cred
    return win, adv


def test_write_read_and_delete_round_trip_with_the_expected_credential_fields(store):
    win, adv = store
    win.write("claudios.test", "geheimes-token ü€")
    kind, persist, user, raw = adv.items["claudios.test"]
    assert (kind, persist, user) == (1, 2, "Claudios") and raw == "geheimes-token ü€".encode()
    assert win.read("claudios.test") == "geheimes-token ü€"
    win.delete("claudios.test")
    assert win.read("claudios.test") is None and win.persistent is True


def test_missing_entries_read_as_none_and_deleting_them_is_fine(store):
    win, _ = store
    assert win.read("gibt-es-nicht") is None
    win.delete("gibt-es-nicht")  # ERROR_NOT_FOUND ist kein Fehler


def test_a_delete_that_really_fails_is_reported(store):
    win, adv = store
    adv.delete_error = 5  # Zugriff verweigert
    with pytest.raises(ClaudiosError):
        win.delete("irgendwas")


@pytest.mark.parametrize("text", ["", "x" * (credstore.MAX_BLOB + 1)])
def test_empty_and_oversized_values_are_refused_before_the_system_call(store, text):
    win, adv = store
    with pytest.raises(ClaudiosError):
        win.write("n", text)
    assert adv.items == {}
    win.write("n", "x" * credstore.MAX_BLOB)  # genau am Limit geht
    assert len(adv.items["n"][3]) == credstore.MAX_BLOB


def test_a_failing_system_write_is_reported_not_swallowed(store):
    win, adv = store
    adv.fail_write = True
    with pytest.raises(ClaudiosError):
        win.write("n", "x")


def test_the_store_choice_falls_back_to_memory_off_windows_or_on_errors(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert isinstance(credstore.get_store(), credstore.MemoryStore) and not credstore.get_store().persistent
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: (_ for _ in ()).throw(OSError("keine dll")), raising=False)
    assert isinstance(credstore.get_store(), credstore.MemoryStore)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: FakeAdvapi(), raising=False)
    assert isinstance(credstore.get_store(), credstore.WindowsStore)


def test_sign_out_clears_the_program_state_even_when_the_stored_token_cannot_be_deleted():
    class Broken(credstore.MemoryStore):
        def delete(self, name):
            raise ClaudiosError(credstore.E.FS_ERROR, reason="credential delete")

    state = session.Session(Broken(persistent=True))
    state.refresh_token, state.access, state.level2 = "r", "a", True
    with pytest.raises(ClaudiosError):
        state.sign_out()
    assert state.refresh_token is None and state.access is None and state.level2 is False and not state.signed_in
