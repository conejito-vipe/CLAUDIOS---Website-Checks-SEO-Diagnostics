"""Programmstart: Splash mit echten Prüfschritten, danach die Einrichtung fehlender Komponenten, dann das Hauptfenster."""
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
from .core._frozen_imports import doh_available
from .core.audit_anchor import default_anchor
from .core.audit_log import AuditLog, use_default_anchor
from .core.errors import catalog
from .core.redact import RedactFilter
from .core.registry import validate_registry
from .i18n.brand import brand_all
from .i18n.strings import TEXTS, n, set_lang, t
from .paths import data_dir
from .settings import load as load_settings
from .ui.boot_install import BootInstaller, BootState, pending_components
from .ui.dialogs import error_info, show_error
from .ui.main_window import MainWindow
from .ui.splash import Splash
from .ui.theme import STYLE
from .ui.theme_extra import EXTRA
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
        state["doh_ok"] = doh_available()
        if not state["doh_ok"]:  # das Programm startet trotzdem, Scans können aber keine Domain auflösen
            logging.getLogger("claudios").error("DNS over HTTPS is not available (dnspython/httpx/httpcore)")

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
    brand_all(TEXTS)  # im Programm immer CLAUDIOS (nach dem Laden aller Textdateien)
    app.setStyleSheet(STYLE + EXTRA)
    app.setFont(QFont("Segoe UI", 10))
    icon = load_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    _setup_logging()
    use_default_anchor(default_anchor)  # Kontrollwert gegen das Löschen des Scan-Protokolls (nur im echten Programm)
    settings = load_settings()
    lang = settings.get("language") or ("de" if QLocale.system().name().startswith("de") else "en")
    set_lang(lang)
    state: dict = {}
    splash = Splash(startup_steps(state))
    windows: list[MainWindow] = []
    installers: list[BootInstaller] = []

    def open_main(failures: list | None = None, titles: dict | None = None) -> None:
        if windows:
            return
        window = MainWindow(settings)
        windows.append(window)
        window.show()
        splash.dismiss()
        if state.get("audit_ok") is False:
            QMessageBox.warning(window, t("app.title"), t("splash.audit_warn"))
        if state.get("doh_ok") is False:
            QMessageBox.warning(window, t("app.title"), t("splash.doh_warn"))
        if failures:
            lines = []
            for name, exc in failures:
                info = error_info(exc)
                lines.append(f"- {(titles or {}).get(name, name)}: {info['code']} {info['title']}")
            QMessageBox.warning(window, t("app.title"),
                                t("boot.failed", count=n(len(failures)), details="\n".join(lines)))

    def begin_install(comps: list) -> None:
        titles = {c.name: c.title for c in comps}
        board = BootState(len(comps))
        installer = BootInstaller(comps)
        installers.append(installer)
        splash.show_skip(True)
        splash.show_progress(0, t("boot.intro"))

        def show() -> None:
            splash.show_progress(board.percent(), t("boot.status", done=n(board.finished), total=n(board.total),
                                                    active=board.active_text(titles)))

        def on_progress(name: str, _phase: str, done: int, total: int) -> None:
            board.update(name, done, total)
            show()

        def on_one(name: str, _error: object) -> None:
            board.finish(name)
            show()

        def on_done(results: list) -> None:
            open_main([(name, exc) for name, exc in results if exc is not None], titles)

        def on_skip() -> None:
            installer.cancel()
            open_main()

        installer.progress.connect(on_progress)
        installer.one_done.connect(on_one)
        installer.done.connect(on_done)
        splash.skipped.connect(on_skip)
        splash.aborted.connect(installer.cancel)
        installer.start()

    def after_steps() -> None:
        comps = pending_components() if settings.get("auto_install") is not False else []
        if comps:
            begin_install(comps)
        else:
            open_main()

    def stop_installers() -> None:
        for installer in installers:
            installer.cancel()
            if not installer.wait(8000):
                installer.terminate()
                installer.wait(2000)

    def on_failed(exc: BaseException) -> None:
        show_error(None, error_info(exc))
        app.quit()

    app.aboutToQuit.connect(stop_installers)
    splash.ready.connect(after_steps)
    splash.failed.connect(on_failed)
    splash.show()
    splash.start()
    return app.exec()
