from types import SimpleNamespace

import pytest

from claudios.core import apikeys, probe_passive, probe_psi, services, thirdparty
from claudios.gsc.credstore import MemoryStore

KEY = "p" * 30


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setitem(apikeys._STATE, "store", MemoryStore())
    return tmp_path


def snap():
    return SimpleNamespace(target=SimpleNamespace(url="https://example.com/", loopback=False))


async def run(monkeypatch, status=429):
    calls = []

    async def fake(method, url, **kw):
        calls.append(kw["params"])
        return status, b"{}", False

    monkeypatch.setattr(thirdparty, "request", fake)
    result = await probe_psi.collect(SimpleNamespace(cancel=None), snap(), None)
    return result, calls


def test_both_google_services_can_have_a_key(env):
    assert set(apikeys.KNOWN) == {"safebrowsing", "pagespeed"}
    apikeys.set_key("pagespeed", KEY)
    assert apikeys.get("pagespeed") == KEY and apikeys.get("safebrowsing") is None


async def test_pagespeed_sends_a_stored_key_only_as_a_parameter(env, monkeypatch):
    services.set_enabled("pagespeed", True)
    apikeys.set_key("pagespeed", KEY)
    result, calls = await run(monkeypatch)
    assert ("key", KEY) in calls[0] and result == {"enabled": True, "skip": "psi_http_429"}
    assert KEY not in repr(result)


async def test_pagespeed_without_a_key_still_asks_but_sends_no_key(env, monkeypatch):
    services.set_enabled("pagespeed", True)
    result, calls = await run(monkeypatch)
    assert all(name != "key" for name, _value in calls[0]) and result["skip"] == "psi_http_429"


def test_the_ghost_fingerprint_follows_the_public_list():
    signs = probe_passive.FINGERPRINTS["Ghost"]
    assert "site unavailable." in signs and "failed to resolve dns path for this host" in signs


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_services_page_stores_the_pagespeed_key_separately(qapp, env):
    from claudios.ui import page_services

    page = page_services.create(None)
    page.retranslate()
    assert not page.psi_delete.isEnabled()
    page.psi_key.setText(KEY)
    page.save_psi_key()
    assert apikeys.has_key("pagespeed") and not apikeys.has_key("safebrowsing")
    assert page.psi_key.text() == "" and page.psi_delete.isEnabled() and page.sb_delete.isEnabled() is False
    page.delete_psi_key()
    assert not apikeys.has_key("pagespeed")
