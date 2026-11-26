import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CLAUDIOS_PLATFORM", "windows")  # die Tests nutzen die Windows-Sperrdatei, auch auf dem Mac

import gc  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Qt sauber abbauen. In der CI (CI=true) und ohne laufende Abdeckungsmessung wird danach der Prozess direkt mit dem
    Testergebnis beendet: Der Abbau von Qt beim Beenden von Python stürzt auf manchen Linux-Rechnern ab (Exit-Code 139),
    obwohl alle Tests bestanden haben, und das würde jede CI rot färben."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            app.processEvents()
    except Exception:  # noqa: BLE001 – Aufräumen darf den Testlauf nie verändern
        pass
    gc.collect()
    coverage_active = "coverage" in sys.modules and getattr(sys.modules["coverage"].Coverage, "current", lambda: None)() is not None
    if os.environ.get("CI") == "true" and not coverage_active:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(exitstatus))
