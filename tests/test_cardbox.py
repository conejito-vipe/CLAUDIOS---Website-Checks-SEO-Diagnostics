"""Karten-Dialoge: Schaltflächen, Escape-Verhalten, Umleitung von QMessageBox, Texte in beiden Sprachen."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from claudios.i18n.strings import TEXTS  # noqa: E402
from claudios.ui import cardbox  # noqa: E402
from claudios.ui.cardbox import SB, MessageCard  # noqa: E402
from claudios.ui.dialogs import AboutDialog, error_card  # noqa: E402

_app = QApplication.instance() or QApplication([])
NAMES = ("information", "warning", "critical", "question")


def test_buttons_follow_flags():
    card = MessageCard(None, "question", "T", "Text", buttons=SB.Yes | SB.No)
    assert set(card.buttons) == {"yes", "no"}


def test_click_sets_choice():
    card = MessageCard(None, "question", "T", "Text", buttons=SB.Yes | SB.No)
    card.buttons["yes"].click()
    assert card.chosen == SB.Yes


def test_close_returns_the_safe_button():
    card = MessageCard(None, "question", "T", "Text", buttons=SB.Yes | SB.No)
    card.reject()
    assert card.chosen == SB.No
    only_ok = MessageCard(None, "info", "T", "Text")
    only_ok.reject()
    assert only_ok.chosen == SB.Ok


def test_default_button_is_marked():
    card = MessageCard(None, "warning", "T", "Text", buttons=SB.Yes | SB.No, default=SB.No)
    assert card.buttons["no"].isDefault()
    assert not card.buttons["yes"].isDefault()


def test_text_is_plain_and_frameless():
    card = MessageCard(None, "info", "T", "<b>x</b>")
    assert bool(card.windowFlags() & Qt.WindowType.FramelessWindowHint)
    labels = card.findChildren(type(card.titlebar.pill))
    assert all(label.textFormat() != Qt.TextFormat.RichText for label in labels)


def test_details_toggle():
    card = MessageCard(None, "info", "T", "Text", details="mehr")
    assert card.details_box is not None and card.details_box.isHidden()
    card._toggle()
    assert not card.details_box.isHidden()


def test_extra_button_runs_its_action():
    called = []
    card = MessageCard(None, "info", "T", "Text", extra=("Ordner", lambda: called.append(1)))
    assert card.extra_button is not None and card.extra_button.text() == "Ordner"
    card.extra_button.click()
    assert called == [1]


def test_install_redirects_static_functions(monkeypatch):
    original = {name: getattr(QMessageBox, name) for name in NAMES}
    try:
        cardbox.install()
        monkeypatch.setattr(MessageCard, "run", lambda self: SB.Yes)
        assert QMessageBox.question(None, "T", "x") == SB.Yes
        assert QMessageBox.warning(None, "T", "x", SB.Yes | SB.No, SB.No) == SB.Yes
    finally:
        for name, func in original.items():
            setattr(QMessageBox, name, func)


def test_error_card_shows_code_log_file_and_folder_button():
    info = {"code": "CLA-TEST", "title": "Titel", "cause": "Ursache", "action": "Tat"}
    card = error_card(None, info)
    texts = " ".join(label.text() for label in card.findChildren(type(card.titlebar.pill)))
    assert "CLA-TEST" in texts and "claudios.log" in texts.lower()
    assert card.extra_button is not None


def test_about_dialog_builds():
    dialog = AboutDialog(None)
    assert bool(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)


def test_card_texts_exist_in_both_languages():
    for key in ("card.ok", "card.yes", "card.no", "card.cancel", "card.close", "card.details",
                "card.details_hide", "card.logs", "card.open_logs"):
        assert TEXTS["de"][key] and TEXTS["en"][key]
