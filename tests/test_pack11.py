"""Paket 11 und 12: Chip-Größe, Abstand im Splash, 250 Seiten, Firefox und WebKit beim Start."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from claudios.core.limits import LIMITS  # noqa: E402
from claudios.ui import boot_install  # noqa: E402
from claudios.ui.splash import Splash  # noqa: E402
from claudios.ui.theme_extra import EXTRA  # noqa: E402

_app = QApplication.instance() or QApplication([])


def test_up_to_250_pages_are_scanned():
    assert LIMITS.pages_level1 == 250 and LIMITS.pages_level2 == 250 and LIMITS.quick_pages == 5


def test_firefox_and_webkit_are_set_up_at_start():
    assert not boot_install.OPTIONAL
    pending = boot_install.pending_components([SimpleNamespace(name="pw-browsers")], lambda comp: "missing")
    assert [comp.name for comp in pending] == ["pw-browsers"]


def test_the_chip_is_14_pixels_high():
    assert "QLabel#pill { font-size: 11px;" in EXTRA and "max-height: 14px" in EXTRA


def test_the_logo_keeps_a_gap_to_the_progress_bar():
    splash = Splash([("splash.s1", 1, lambda: None)])
    splash.show_progress(40, "Komponenten werden eingerichtet " * 6)
    splash.skip_btn.setVisible(True)  # ungünstigster Fall: alle Elemente sichtbar
    splash.show()
    _app.processEvents()
    assert splash.logo.geometry().bottom() + 10 <= splash.bottom.geometry().top()
    splash.dismiss()
