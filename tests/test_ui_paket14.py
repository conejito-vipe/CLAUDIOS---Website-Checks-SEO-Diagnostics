"""Einstellung der Update-Prüfung und Uninstall-Dialog im Karten-Stil."""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

from PySide6.QtWidgets import QApplication, QPushButton

from claudios import settings as settings_module
from claudios.i18n.strings import get_lang, set_lang, t
from claudios.ui.cardbox import CardDialog
from claudios.ui.components_page import UninstallDialog
from claudios.ui.pages import SettingsPage

_APP = QApplication.instance() or QApplication([])


def _redirect_settings(monkeypatch, tmp_path):
    path = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(settings_module, "_file", lambda: path)
    return path


def test_update_switch_default_is_on_and_off_is_stored(monkeypatch, tmp_path):
    path = _redirect_settings(monkeypatch, tmp_path)
    settings = {"language": "de", "allow_localhost": False}
    page = SettingsPage(settings)
    assert page.updates.isChecked()
    page.updates.setChecked(False)
    assert settings["update_check"] is False
    assert json.loads(path.read_text("utf-8"))["update_check"] is False
    page.updates.setChecked(True)
    assert "update_check" not in settings
    assert "update_check" not in json.loads(path.read_text("utf-8"))
    assert settings_module.load().get("update_check") is None


def test_update_switch_shows_stored_off_state():
    assert SettingsPage({"update_check": False}).updates.isChecked() is False


def test_update_switch_texts_exist_in_both_languages():
    previous = get_lang()
    try:
        for lang in ("de", "en"):
            set_lang(lang)
            page = SettingsPage({})
            page.retranslate()
            assert page.updates.text() and page.update_note.text()
    finally:
        set_lang(previous)


def test_uninstall_dialog_is_a_card_with_working_selection():
    items = [NS(kind="tool", key="cache", title="Cache", size=2048, default=True),
             NS(kind="tool", key="logs", title="Logs", size=0, default=False)]
    dialog = UninstallDialog(None, items, [])
    assert isinstance(dialog, CardDialog)
    assert dialog.selected() == ["cache"]
    dialog._boxes["logs"].setChecked(True)
    assert dialog.selected() == ["cache", "logs"]
    assert dialog.warn.text() == ""
    texts = {button.text() for button in dialog.findChildren(QPushButton)}
    assert t("unin.ok") in texts and t("unin.cancel") in texts
