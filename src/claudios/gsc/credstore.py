"""Speicher für das Google-Refresh-Token und den importierten Client: Windows-Anmeldeinformationsspeicher
(Credential Manager). Nie eine Datei. Auf anderen Systemen und bei Fehlern gibt es nur einen Speicher im
Arbeitsspeicher ohne Dauerhaftigkeit."""
from __future__ import annotations

import sys

from ..core.errors import ClaudiosError, ErrorCode as E

MAX_BLOB = 2560  # CRED_MAX_CREDENTIAL_BLOB_SIZE von Windows
ERROR_NOT_FOUND = 1168


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
        """Löscht den Eintrag. „Nicht vorhanden“ ist in Ordnung; jeder andere Fehler wird gemeldet, damit ein Token nie
        unbemerkt im Speicher bleibt, obwohl der Nutzer sich abgemeldet hat."""
        if not self._adv.CredDeleteW(name, 1, 0) and self._ct.get_last_error() != ERROR_NOT_FOUND:
            raise ClaudiosError(E.FS_ERROR, reason="credential delete")


ERR_SEC_NOT_FOUND = -25300  # errSecItemNotFound
ERR_SEC_DUPLICATE = -25299  # errSecDuplicateItem


class MacStore:
    """Schlüsselbund von macOS (Security.framework, nur Programmschnittstellen; das Geheimnis steht nie in einer
    Kommandozeile). Dienstname CLAUDIOS, Kontoname = Name des Eintrags."""
    persistent = True
    SERVICE = b"CLAUDIOS"

    def __init__(self, sec=None, cf=None) -> None:
        import ctypes
        import ctypes.util

        if sec is None or cf is None:
            sec = ctypes.CDLL(ctypes.util.find_library("Security") or "/System/Library/Frameworks/Security.framework/Security")
            cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation")
                             or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            u32, vp, cp = ctypes.c_uint32, ctypes.c_void_p, ctypes.c_char_p
            sec.SecKeychainAddGenericPassword.argtypes = [vp, u32, cp, u32, cp, u32, vp, ctypes.POINTER(vp)]
            sec.SecKeychainAddGenericPassword.restype = ctypes.c_int32
            sec.SecKeychainFindGenericPassword.argtypes = [vp, u32, cp, u32, cp, ctypes.POINTER(u32),
                                                           ctypes.POINTER(vp), ctypes.POINTER(vp)]
            sec.SecKeychainFindGenericPassword.restype = ctypes.c_int32
            sec.SecKeychainItemModifyAttributesAndData.argtypes = [vp, vp, u32, vp]
            sec.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
            sec.SecKeychainItemFreeContent.argtypes = [vp, vp]
            sec.SecKeychainItemFreeContent.restype = ctypes.c_int32
            sec.SecKeychainItemDelete.argtypes = [vp]
            sec.SecKeychainItemDelete.restype = ctypes.c_int32
            cf.CFRelease.argtypes = [vp]
        self._ct, self._sec, self._cf = ctypes, sec, cf

    def _find(self, name: str, want_data: bool):
        """(Status, Wert oder None, Eintragsverweis oder None)."""
        ct = self._ct
        account = name.encode("utf-8")
        length, data, item = ct.c_uint32(0), ct.c_void_p(), ct.c_void_p()
        status = self._sec.SecKeychainFindGenericPassword(
            None, len(self.SERVICE), self.SERVICE, len(account), account,
            ct.byref(length) if want_data else None, ct.byref(data) if want_data else None, ct.byref(item))
        if status != 0:
            return status, None, None
        value = None
        if want_data:
            value = ct.string_at(data, length.value).decode("utf-8", "replace")
            self._sec.SecKeychainItemFreeContent(None, data)
        return 0, value, item

    def write(self, name: str, text: str) -> None:
        raw, account = text.encode("utf-8"), name.encode("utf-8")
        status = self._sec.SecKeychainAddGenericPassword(None, len(self.SERVICE), self.SERVICE, len(account), account,
                                                         len(raw), raw, None)
        if status == ERR_SEC_DUPLICATE:  # vorhanden: Wert ersetzen
            found, _value, item = self._find(name, want_data=False)
            if found != 0:
                raise ClaudiosError(E.FS_ERROR, reason="credential write")
            try:
                status = self._sec.SecKeychainItemModifyAttributesAndData(item, None, len(raw), raw)
            finally:
                self._cf.CFRelease(item)
        if status != 0:
            raise ClaudiosError(E.FS_ERROR, reason="credential write")

    def read(self, name: str) -> str | None:
        status, value, item = self._find(name, want_data=True)
        if status == ERR_SEC_NOT_FOUND:
            return None
        if status != 0:
            raise ClaudiosError(E.FS_ERROR, reason="credential read")
        self._cf.CFRelease(item)
        return value

    def delete(self, name: str) -> None:
        """Wie unter Windows: „nicht vorhanden“ ist in Ordnung, jeder andere Fehler wird gemeldet."""
        status, _value, item = self._find(name, want_data=False)
        if status == ERR_SEC_NOT_FOUND:
            return
        if status != 0:
            raise ClaudiosError(E.FS_ERROR, reason="credential delete")
        try:
            if self._sec.SecKeychainItemDelete(item) != 0:
                raise ClaudiosError(E.FS_ERROR, reason="credential delete")
        finally:
            self._cf.CFRelease(item)


def get_store():
    if sys.platform == "win32":
        try:
            return WindowsStore()
        except (OSError, AttributeError):
            pass
    if sys.platform == "darwin":
        try:
            return MacStore()
        except (OSError, AttributeError):
            pass
    return MemoryStore(persistent=False)
