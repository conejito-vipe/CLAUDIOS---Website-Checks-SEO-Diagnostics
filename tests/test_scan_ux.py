import json
import string
import time

import pytest

from claudios.core import apikeys, services
from claudios.core._frozen_imports import doh_available
from claudios.core.limits import LIMITS
from claudios.gsc.credstore import MemoryStore
from claudios.i18n.strings import TEXTS, get_lang, set_lang
from claudios.ui import cooldown
from claudios.ui.urlinput import clean_input


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setitem(apikeys._STATE, "store", MemoryStore())
    return tmp_path


@pytest.mark.parametrize("raw,local,expected", [
    ("example.com", False, "example.com"), ("  https://example.com ", False, "https://example.com"),
    ("http://example.com/x", False, "https://example.com/x"), ("HTTP://Example.com", False, "https://Example.com"),
    ("http://localhost:8000", False, "https://localhost:8000"), ("http://localhost:8000", True, "http://localhost:8000"),
    ("http://example.com", True, "https://example.com"), ("", False, "")])
def test_http_becomes_https_but_local_addresses_stay_when_allowed(raw, local, expected):
    assert clean_input(raw, local) == expected


def test_the_limits_follow_the_windows_test():
    assert (LIMITS.cooldown_seconds, LIMITS.scans_per_domain_day_level1, LIMITS.scans_per_domain_day_level2) == (30, 5, 12)


def test_the_cooldown_counts_from_the_last_scan_start(tmp_path):
    path = tmp_path / "audit.jsonl"
    assert cooldown.remaining(path, now=1000.0) == 0  # keine Datei
    lines = [{"t": 900.0, "event": "scan_start"}, {"t": 990.0, "event": "scan_start"}, {"t": 999.0, "event": "scan_end"}]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\nkein json\n", "utf-8")
    assert cooldown.remaining(path, now=1000.0) == LIMITS.cooldown_seconds - 10
    assert cooldown.remaining(path, now=990.0 + LIMITS.cooldown_seconds + 5) == 0


def test_dns_over_https_is_available_in_the_test_environment():
    assert doh_available() is True


def test_the_scan_texts_exist_in_both_languages_with_the_same_placeholders():
    keys = [k for k in TEXTS["de"] if k.startswith(("scan.profile_info", "scan.expert", "scan.cooldown", "scan.ext_ask"))]
    keys.append("splash.doh_warn")
    assert len(keys) >= 10
    for key in keys:
        names = [{f for _lit, f, _spec, _conv in string.Formatter().parse(TEXTS[lang][key]) if f}
                 for lang in ("de", "en")]
        assert TEXTS["de"][key].strip() and TEXTS["en"][key].strip() and names[0] == names[1], key
    assert set(TEXTS["de"]) == set(TEXTS["en"])


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_expert_box_asks_before_it_switches_a_service_on(qapp, env, monkeypatch):
    from claudios.ui import expert_box

    box = expert_box.ExpertBox()
    box.retranslate()
    monkeypatch.setattr(expert_box, "_confirm", lambda parent, text: False)
    box.rdap.setChecked(True)
    assert not services.enabled("rdap") and not box.rdap.isChecked()
    monkeypatch.setattr(expert_box, "_confirm", lambda parent, text: True)
    box.rdap.setChecked(True)
    box.sb.setChecked(True)
    box.psi.setChecked(True)
    assert services.enabled("rdap") and services.enabled("safebrowsing") and services.enabled("pagespeed")
    assert len(box.external_names()) == 2  # Safe Browsing ohne Schlüssel sendet nichts
    assert box.hint.text().strip() != ""


def _page():
    from claudios.ui.pages import ScanPage

    page = ScanPage(lambda: {"allow_localhost": False})
    page.retranslate()
    return page


def test_the_scan_asks_before_it_sends_data_to_third_parties(qapp, env, monkeypatch):
    from claudios.ui import pages

    services.set_enabled("rdap", True)
    asked = []
    monkeypatch.setattr(pages, "_confirm", lambda parent, text: asked.append(text) or False)
    page = _page()
    page.url.setText("example.com")
    page.start()
    assert len(asked) == 1 and page._thread is None


def test_the_scan_gets_an_https_address_and_shows_the_profile_text(qapp, env, monkeypatch):
    from PySide6.QtCore import QObject, Signal

    from claudios.ui import pages

    class FakeThread(QObject):
        progress, done, failed, finished = Signal(str, int, int), Signal(object), Signal(object), Signal()
        kwargs = None

        def __init__(self, kwargs):
            super().__init__()
            FakeThread.kwargs = kwargs

        def start(self):
            pass

        def cancel(self):
            pass

        def isRunning(self):  # noqa: N802 (Name von Qt)
            return False

    old = get_lang()
    try:
        set_lang("de")
        monkeypatch.setattr(pages, "ScanThread", FakeThread)
        page = _page()
        assert "Standard" in page.profile_info.text()
        page.profile.setCurrentIndex(2)
        assert "Firefox" in page.profile_info.text()
        page.url.setText("http://example.com")
        page.start()
        assert FakeThread.kwargs["raw_url"] == "https://example.com" and page.url.text() == "https://example.com"
        page._cleanup()
    finally:
        set_lang(old)


def test_a_recent_scan_shows_the_countdown(qapp, env):
    from claudios.paths import data_dir

    page = _page()
    audit = data_dir() / "logs" / "audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps({"t": time.time() - 10, "event": "scan_start"}) + "\n", "utf-8")
    page._start_cooldown()
    assert not page.cool_bar.isHidden() and 0 < page.cool_bar.value() <= LIMITS.cooldown_seconds - 9
    assert page._cool_timer.isActive()
    page.shutdown()
    audit.write_text("", "utf-8")
    page._start_cooldown()
    assert page.cool_bar.isHidden()
