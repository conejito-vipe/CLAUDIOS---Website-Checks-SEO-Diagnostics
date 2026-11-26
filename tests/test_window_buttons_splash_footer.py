"""Splash-Maße, verzögerter Knopf, Fensterknöpfe, Autor-Link in der Fußzeile."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cssutil import rules  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from claudios.i18n.strings import get_lang, set_lang  # noqa: E402
from claudios.i18n.strings_author import AUTHOR  # noqa: E402
from claudios.ui import splash as splash_module  # noqa: E402
from claudios.ui.footer_link import PROFILE_URL, LinkFooter  # noqa: E402
from claudios.ui.splash import Splash  # noqa: E402
from claudios.ui.theme import STYLE  # noqa: E402
from claudios.ui.theme_extra import EXTRA  # noqa: E402
from claudios.ui.widgets import TitleBar  # noqa: E402

_app = QApplication.instance() or QApplication([])


def test_splash_proportions():
    assert splash_module.LOGO_HEIGHT == 251 and splash_module.LOGO_GAP == 14 and splash_module.SKIP_DELAY_MS == 20000


def test_skip_button_appears_only_after_the_delay():
    splash = Splash([("splash.s1", 1, lambda: None)])
    splash.show_skip(True)
    assert splash.skip_btn.isHidden()
    splash.show_skip(True, delay_ms=0)
    assert not splash.skip_btn.isHidden()
    splash.show_skip(False)
    assert splash.skip_btn.isHidden()


def test_window_buttons_have_hover_roles():
    bar = TitleBar(False)
    assert bar.btn_close.property("role") == "close" and bar.btn_min.property("role") == "min"
    sheet = rules(STYLE + EXTRA)
    assert sheet['QPushButton#winbtn[role="close"]:hover']["background"] == "#C62828"
    assert sheet['QPushButton#winbtn[role="min"]:hover']["background"] == "#EE6A12"


def test_the_author_in_the_footer_is_an_orange_link():
    old = get_lang()
    try:
        for lang in ("de", "en"):
            set_lang(lang)
            footer = LinkFooter()
            footer.retranslate()
            assert footer.author.text() == AUTHOR and AUTHOR not in footer.before.text()
            assert footer.tail.text() and footer.author.toolTip() == PROFILE_URL
    finally:
        set_lang(old)
    assert rules(STYLE + EXTRA)["QPushButton#authorlink"]["color"] == "#EE6A12"
