"""Sicherheitsfrage beim Schließen, Ladekreis beim Sprachwechsel, Beschriftung unter dem Papierkorb, orange Reiter."""
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from claudios.i18n.strings import set_lang, t  # noqa: E402
from claudios.ui import main_window  # noqa: E402
from claudios.ui.main_window import MainWindow  # noqa: E402
from claudios.ui.theme import ORANGE  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _window():
    return MainWindow({"language": "de", "allow_localhost": False})


def test_closing_asks_first_and_keeps_the_window_on_no(monkeypatch):
    window = _window()
    window.confirm_close = True
    answers = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: (answers.append(self.text()), self.setProperty("p", len(answers)))[0])
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: self.buttons()[0] if self.property("p") == 2 else self.buttons()[1])
    window.show()
    window.close()
    assert window.isVisible() and answers[0] == t("close.ask")  # Antwort „Weiter arbeiten“: bleibt offen
    window.close()
    assert not window.isVisible()


def test_a_running_scan_gets_the_stronger_question(monkeypatch):
    window = _window()
    window.confirm_close = True
    window._scan_running = True
    seen = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: seen.append(self.text()))
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[1])
    assert window._really_close() is False and seen == [t("close.running")]


def test_without_the_flag_nothing_is_asked():
    window = _window()
    assert window.confirm_close is False and window._really_close() is True


def test_the_language_switch_shows_a_spinner_only_while_it_works():
    window = _window()
    states = []
    original = main_window.MainWindow.retranslate
    window.retranslate = lambda: states.append(window.titlebar.spinner.active)
    try:
        window.set_language("en")
    finally:
        window.retranslate = original.__get__(window)
        set_lang("de")
    assert states == [True] and not window.titlebar.spinner.active


def test_the_trash_can_has_a_label_and_the_selected_tab_is_an_orange_chip():
    window = _window()
    assert window.uninstall_lbl.text() == t("app.uninstall.short") == "Deinstallieren"
    from claudios.ui.theme_extra import full_style
    css = full_style()
    assert "QTabBar::tab:selected { background: " + ORANGE in css


def test_the_navigation_rail_always_fits_without_overlap_at_the_minimum_size():
    window = _window()
    window.resize(window.minimumSize())
    window.show()
    _APP.processEvents()
    nav, button = window.nav.geometry(), window.uninstall_btn.geometry()
    assert nav.bottom() < button.top()
    visible = [i for i in range(window.nav.count()) if not window.nav.item(i).isHidden()]
    assert "nav.scan" in [window.nav_keys[i] for i in visible]
    for i in visible:  # jeder Eintrag liegt vollständig im sichtbaren Bereich der Leiste
        rect = window.nav.visualItemRect(window.nav.item(i))
        assert 0 <= rect.top() and rect.bottom() <= window.nav.viewport().height()
