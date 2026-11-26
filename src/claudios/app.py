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
from .core import dohfallback, fsutil
from .core._frozen_imports import doh_status
from .core.audit_anchor import default_anchor
from .core.audit_log import AuditLog, use_default_anchor
from .core.errorlog import install as install_error_logging, log_startup
from .core.errors import catalog
from .core.redact import RedactFilter
from .core.registry import validate_registry
from .i18n.brand import brand_all
from .i18n.strings import TEXTS, n, set_lang, t
from .paths import LOG_NAME, data_dir
from .settings import load as load_settings
from .ui.boot_install import BootInstaller, BootState, pending_components
from .ui.cardbox import MessageCard, install as install_cards
from .ui.dialogs import error_info, show_error
from .ui.instance import acquire
from .ui.logfolder import open_logs
from .ui.main_window import MainWindow
from .ui.splash import Splash
from .ui.theme import STYLE
from .ui.theme_extra import EXTRA
from .ui.update_check import start_update_check
from .ui.widgets import load_icon

Step = tuple[str, int, Callable[[], None]]
log = logging.getLogger("claudios")


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
        ok, detail = doh_status()
        state["doh_ok"] = ok
        if ok:
            log.info("DNS over HTTPS check: %s", detail)
        else:  # das Programm startet trotzdem, Scans können aber keine Domain auflösen
            log.error("DNS over HTTPS is not available: %s", detail)

    def check_audit() -> None:
        try:
            state["audit_ok"] = AuditLog(data_dir() / "logs" / "audit.jsonl").verify()
        except (ValueError, KeyError, TypeError, OSError):  # unlesbares Protokoll: nur warnen, nicht abstürzen
            state["audit_ok"] = False

    return [("splash.s1", 1, check_dirs), ("splash.s2", 1, load_catalog), ("splash.s3", 2, check_registry),
            ("splash.s4", 3, load_psl), ("splash.s5", 1, check_audit)]


def _setup_logging() -> None:
    logs = data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(logs / LOG_NAME, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.addFilter(RedactFilter())  # keine Geheimnisse in Logs
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def main() -> int:
    if "--selftest" in sys.argv:  # Prüfung des gebauten Programms, ohne Splash und ohne Einzelinstanz-Sperre
        from .selftest import run as run_selftest

        return run_selftest()
    app = QApplication(sys.argv)
    app.setApplicationName("CLAUDIOS")
    brand_all(TEXTS)  # im Programm immer CLAUDIOS (nach dem Laden aller Textdateien)
    app.setStyleSheet(STYLE + EXTRA)
    install_cards()  # alle Meldungen im Stil des Splash (statt Windows-Titelleiste)
    app.setFont(QFont("Helvetica Neue" if sys.platform == "darwin" else "Segoe UI", 10 if sys.platform != "darwin" else 13))
    icon = load_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    _setup_logging()
    install_error_logging()  # jeder Fehler und jede unbehandelte Ausnahme landet im Protokoll
    from .core.crashlog import install as install_crash_log

    install_crash_log()  # Absturz-Spur und Wächter gegen Einfrieren (logs/CLAUDIOS-crash.log)
    log_startup()
    fsutil.harden()  # Wiederholungen bei Dateisperren durch Virenscanner (Windows)
    log.info("DNS over HTTPS mode: %s", dohfallback.install_if_needed())
    use_default_anchor(default_anchor)  # Kontrollwert gegen das Löschen des Scan-Protokolls (nur im echten Programm)
    settings = load_settings()
    lang = settings.get("language") or ("de" if QLocale.system().name().startswith("de") else "en")
    set_lang(lang)
    instance_lock = acquire(data_dir() / "CLAUDIOS.lock")
    if instance_lock is None:
        log.warning("CLAUDIOS is already running, this instance exits")
        MessageCard(None, "info", t("app.title"), t("app.running")).run()
        return 0
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
        start_update_check(window, settings)  # nur im installierten Programm
        if state.get("audit_ok") is False:
            QMessageBox.warning(window, t("app.title"), t("splash.audit_warn"))
        if state.get("doh_ok") is False:
            QMessageBox.warning(window, t("app.title"), t("splash.doh_warn"))
        if failures:
            lines = []
            for name, exc in failures:
                info = error_info(exc)
                log.error("component %s failed: %s %r", name, info["code"], exc)
                lines.append(f"- {(titles or {}).get(name, name)}: {info['code']} {info['title']}")
            MessageCard(window, "warning", t("app.title"),
                        t("boot.failed", count=n(len(failures)), details="\n".join(lines)),
                        extra=(t("card.open_logs"), open_logs)).run()

    def begin_install(comps: list) -> None:
        titles = {c.name: c.title for c in comps}
        board = BootState(len(comps))
        installer = BootInstaller(comps)
        installers.append(installer)
        started: set[str] = set()
        splash.show_skip(True)
        splash.show_progress(0, t("boot.intro"))

        def show() -> None:
            splash.show_progress(board.percent(), t("boot.status", done=n(board.finished), total=n(board.total),
                                                    active=board.active_text(titles)))

        def on_progress(name: str, _phase: str, done: int, total: int) -> None:
            if name not in started:  # Zeitstempel im Protokoll zeigen, wie lange eine Komponente braucht
                started.add(name)
                log.info("component %s: started", name)
            board.update(name, done, total)
            show()

        def on_one(name: str, error: object) -> None:
            log.info("component %s: %s", name, "finished" if error is None else f"failed ({error!r})")
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
        log.error("startup failed: %r", exc)
        show_error(None, error_info(exc))
        app.quit()

    app.aboutToQuit.connect(stop_installers)
    splash.ready.connect(after_steps)
    splash.failed.connect(on_failed)
    splash.show()
    splash.start()
    code = app.exec()
    instance_lock.unlock()
    return code
