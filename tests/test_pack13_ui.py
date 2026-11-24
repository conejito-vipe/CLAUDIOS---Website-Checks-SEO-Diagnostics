"""Paket 13, Oberfläche: Livebereich in den Ergebnissen, Navigationsbalken, Verlauf nach dem Neustart.
Seit Paket 25 springt der Scan nicht mehr während des Laufs in die Ergebnisse."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from claudios.i18n.strings import get_lang, set_lang  # noqa: E402
from claudios.report import history  # noqa: E402
from claudios.ui.main_window import MainWindow  # noqa: E402
from claudios.ui.results_page import ResultsPage  # noqa: E402

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    old = get_lang()
    set_lang("de")
    yield tmp_path
    set_lang(old)


def test_the_live_area_shows_and_hides(env):
    page = ResultsPage()
    assert page.live_box.isHidden()
    page.show_live("Prüfung 3 / 90", 70)
    assert not page.live_box.isHidden() and page.live_bar.value() == 70 and "Prüfung 3 / 90" in page.live_text.text()
    page.hide_live()
    assert page.live_box.isHidden()


def test_the_last_saved_scan_is_shown_after_a_restart(env):
    history.set_enabled(True)
    history.save({"version": 1, "saved": "2026-11-21T10:00:00+00:00", "host": "example.test", "level": 1,
                  "profile": "standard", "status": "complete", "score": 88, "categories": {},
                  "findings": [{"check_id": "SEC-HDR-001", "severity": 2, "msg_de": "Keine CSP", "msg_en": "No CSP",
                                "count": 3}]})
    page = ResultsPage()
    page.retranslate()
    assert page.table.rowCount() == 1 and "example.test" in page.summary.text() and "88" in page.summary.text()


def test_the_navigation_box_follows_the_scan_and_the_results_wait_for_the_end(env):
    window = MainWindow({"language": "de", "allow_localhost": False})
    assert window.live_box.isHidden()
    window.scan.running_changed.emit(True)
    assert not window.live_box.isHidden()
    window.scan.activity.emit("Seiten geladen: 12 / 250", 10, "crawl")
    assert window.nav.currentRow() == 0 and window.live_bar.value() == 10
    window.scan.activity.emit("Prüfung 3 / 90: SEC-HDR-001", 62, "check")
    assert window.nav.currentRow() == 0 and window.results.live_box.isHidden()
    window.scan.running_changed.emit(False)
    assert window.live_box.isHidden() and window.results.live_box.isHidden()
