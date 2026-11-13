"""Programmstart: Splash mit echten Prüfschritten, danach das Hauptfenster."""
from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

from publicsuffix2 import get_sld
from PySide6.QtCore import QLocale
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from .checks import load_all
from .core.audit_log import AuditLog
from .core.errors import catalog
from .core.redact import RedactFilter
from .core.registry import validate_registry
from .i18n.strings import set_lang, t
from .paths import data_dir
from .settings import load as load_settings
from .ui.dialogs import error_info, show_error
from .ui.main_window import MainWindow
from .ui.splash import Splash
from .ui.theme import STYLE
from .ui.widgets import load_icon

Step = tuple[str, int, Callable[[], None]]


def startup_steps(state: dict) -> list[Step]:
    def check_dirs() -> None:
        base = data_dir()
        for sub in ("logs", "config", "cache"):
            (base / sub).mkdir(parents=True, exist_ok=True)
        probe = base / "cache" / ".probe"
        probe.write_text("ok", "utf-8")
        probe.unlink()

    def load_catalog() -> None:
        if not catalog():
            raise RuntimeError("error catalog is empty")

    def check_registry() -> None:
        load_all()
        errors = validate_registry()
        if errors:
            raise RuntimeError(f"registry: {errors[0]}")

    def load_psl() -> None:
        get_sld("example.co.uk")

    def check_audit() -> None:
        state["audit_ok"] = AuditLog(data_dir() / "logs" / "audit.jsonl").verify()

    return [("splash.s1", 1, check_dirs), ("splash.s2", 1, load_catalog), ("splash.s3", 2, check_registry),
            ("splash.s4", 3, load_psl), ("splash.s5", 1, check_audit)]


def _setup_logging() -> None:
    logs = data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / "claudios.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.addFilter(RedactFilter())  # keine Geheimnisse in Logs
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Claudios")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    icon = load_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    _setup_logging()
    settings = load_settings()
    lang = settings.get("language") or ("de" if QLocale.system().name().startswith("de") else "en")
    set_lang(lang)
    state: dict = {}
    splash = Splash(startup_steps(state))
    windows: list[MainWindow] = []

    def open_main() -> None:
        window = MainWindow(settings)
        windows.append(window)
        window.show()
        splash.dismiss()
        if state.get("audit_ok") is False:
            QMessageBox.warning(window, t("app.title"), t("splash.audit_warn"))

    def on_failed(exc: BaseException) -> None:
        show_error(None, error_info(exc))
        app.quit()

    splash.ready.connect(open_main)
    splash.failed.connect(on_failed)
    splash.show()
    splash.start()
    return app.exec()
