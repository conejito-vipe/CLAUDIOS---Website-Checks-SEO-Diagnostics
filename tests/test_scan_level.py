from types import SimpleNamespace

import pytest

from claudios.i18n.strings import TEXTS, get_lang, set_lang, t
from claudios.ui.levelinfo import KEYS, level_info

SITES = [{"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"},
         {"siteUrl": "https://www.other.test/", "permissionLevel": "siteRestrictedUser"}]


def fake(level2=True, sites=None):
    return SimpleNamespace(level2=level2, sites=SITES if sites is None else sites)


def test_without_level_2_the_level_is_1_whatever_the_properties_are():
    assert level_info("example.com", False, fake(level2=False)).state == "level1"


def test_a_covered_domain_gets_level_2_with_its_property():
    info = level_info("shop.example.com", False, fake())
    assert (info.level, info.state, info.prop) == (2, "level2", "sc-domain:example.com")


def test_an_uncovered_domain_or_a_restricted_user_is_flagged():
    assert level_info("other.org", False, fake()).state == "nomatch"
    assert level_info("www.other.test", False, fake()).state == "nomatch"  # nur eingeschränkter Zugriff


def test_without_a_valid_address_and_for_localhost_nothing_is_promised():
    assert level_info("", False, fake()).state == "armed"
    assert level_info("a b", False, fake()).state == "armed"
    assert level_info("http://localhost:8000", True, fake()) == level_info("localhost", True, fake())
    assert level_info("http://localhost:8000", True, fake()).level == 1


def test_all_texts_exist_in_both_languages_and_format_cleanly():
    for key in [*KEYS.values(), "scan.google", "scan.done_level"]:
        for lang in ("de", "en"):
            assert TEXTS[lang][key].strip()
            TEXTS[lang][key].format_map({"pages": "25", "depth": "6", "prop": "x", "status": "s", "level": "2"})
    assert set(TEXTS["de"]) == set(TEXTS["en"])


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_scan_page_shows_the_level_and_the_google_button_opens_the_console_page(qapp, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from claudios.gsc import session
    from claudios.ui.pages import ScanPage

    class Nav:
        row = None

        def setCurrentRow(self, row):  # noqa: N802 (Name von Qt)
            self.row = row

    old = get_lang()
    try:
        set_lang("de")
        monkeypatch.setattr(session, "SESSION", fake(level2=False))
        page = ScanPage(lambda: {"allow_localhost": False})
        page.retranslate()
        assert page.google.isEnabled() and "Stufe 1" in page.level_lbl.text()
        monkeypatch.setattr(session, "SESSION", fake())
        page.url.setText("example.com")
        assert "sc-domain:example.com" in page.level_lbl.text() and "250" in page.level_lbl.text()
        page.url.setText("other.org")
        assert page.level_lbl.text() == t("scan.level_nomatch")
        window = QWidget()
        window.nav, window.nav_keys = Nav(), ("nav.scan", "nav.gsc")
        page.setParent(window)
        page.open_google()
        assert window.nav.row == 1
    finally:
        set_lang(old)
