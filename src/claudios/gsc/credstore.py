"""Speicher für das Google-Refresh-Token und den importierten Client: Windows-Anmeldeinformationsspeicher
(Credential Manager). Nie eine Datei. Auf anderen Systemen und bei Fehlern gibt es nur einen Speicher im
Arbeitsspeicher ohne Dauerhaftigkeit."""
from __future__ import annotations

import sys

from ..core.errors import ClaudiosError, ErrorCode as E

MAX_BLOB = 2560


class MemoryStore:
    def __init__(self, persistent: bool = False) -> None:
        self.persistent = persistent
        self.data: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.data.get(name)

    def write(self, name: str, text: str) -> None:
        self.data[name] = text

    def delete(self, name: str) -> None:
        self.data.pop(name, None)


class WindowsStore:
    persistent = True

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        adv.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        adv.CredWriteW.restype = wintypes.BOOL
        adv.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        adv.CredReadW.restype = wintypes.BOOL
        adv.CredFree.argtypes = [ctypes.c_void_p]
        adv.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        adv.CredDeleteW.restype = wintypes.BOOL
        self._ct, self._adv, self._cred = ctypes, adv, CREDENTIAL

    def write(self, name: str, text: str) -> None:
        ct = self._ct
        raw = text.encode("utf-8")
        if not raw or len(raw) > MAX_BLOB:
            raise ClaudiosError(E.FS_ERROR, reason="credential size")
        blob = (ct.c_ubyte * len(raw)).from_buffer_copy(raw)
        cred = self._cred()
        cred.Type = 1  # CRED_TYPE_GENERIC
        cred.TargetName = name
        cred.CredentialBlobSize = len(raw)
        cred.CredentialBlob = ct.cast(blob, ct.POINTER(ct.c_ubyte))
        cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = "Claudios"
        if not self._adv.CredWriteW(ct.byref(cred), 0):
            raise ClaudiosError(E.FS_ERROR, reason="credential store")

    def read(self, name: str) -> str | None:
        ct = self._ct
        ptr = ct.POINTER(self._cred)()
        if not self._adv.CredReadW(name, 1, 0, ct.byref(ptr)):
            return None
        try:
            cred = ptr.contents
            raw = ct.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        finally:
            self._adv.CredFree(ct.cast(ptr, ct.c_void_p))
        return raw.decode("utf-8", errors="replace")

    def delete(self, name: str) -> None:
        self._adv.CredDeleteW(name, 1, 0)


def get_store():
    if sys.platform == "win32":
        try:
            return WindowsStore()
        except (OSError, AttributeError):
            pass
    return MemoryStore(persistent=False)
