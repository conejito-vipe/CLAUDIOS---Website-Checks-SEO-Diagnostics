"""Programmstart: Prüfschritte, Protokoll ohne Geheimnisse, Einzelinstanz, Hauptfenster, Einrichtung der Komponenten."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from claudios import app
from claudios.core.errors import ClaudiosError, ErrorCode as E


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "data_dir", lambda: tmp_path / "data")
    return tmp_path / "data"


def steps(state=None):
    state = {} if state is None else state
    return state, {name: fn for name, _w, fn in app.startup_steps(state)}


def test_all_five_startup_steps_pass_on_a_healthy_system(home):
    state, by_name = steps()
    assert list(by_name) == ["splash.s1", "splash.s2", "splash.s3", "splash.s4", "splash.s5"]
    for fn in by_name.values():
        fn()
    assert (home / "logs").is_dir() and (home / "config").is_dir() and not (home / "cache" / ".probe").exists()
    assert state["audit_ok"] is True and "doh_ok" in state


def test_an_empty_catalog_or_a_broken_registry_stops_the_start_with_a_reason(home, monkeypatch):
    _s, by_name = steps()
    monkeypatch.setattr(app, "catalog", lambda: {})
    with pytest.raises(RuntimeError, match="catalog"):
        by_name["splash.s2"]()
    monkeypatch.setattr(app, "load_all", lambda: None)
    monkeypatch.setattr(app, "validate_registry", lambda: ["doppelte ID"])
    with pytest.raises(RuntimeError, match="doppelte ID"):
        by_name["splash.s3"]()


def test_missing_doh_only_warns_and_an_unreadable_audit_log_never_crashes(home, monkeypatch):
    state, by_name = steps()
    monkeypatch.setattr(app, "doh_status", lambda: (False, "fehlt"))
    by_name["splash.s4"]()
    assert state["doh_ok"] is False

    class Broken:
        def __init__(self, _path):
            pass

        def verify(self):
            raise ValueError("kaputt")

    monkeypatch.setattr(app, "AuditLog", Broken)
    by_name["splash.s5"]()
    assert state["audit_ok"] is False


def test_the_log_file_never_contains_secrets(home):
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        app._setup_logging()
        added = [h for h in root.handlers if h not in before]
        logging.getLogger("claudios.test").error("Anmeldung mit Authorization: Bearer abcdef0123456789secretvalue")
        for h in added:
            h.flush()
        text = (home / "logs" / app.LOG_NAME).read_text("utf-8")
        assert "abcdef0123456789secretvalue" not in text and "Anmeldung" in text
    finally:
        for h in root.handlers[:]:
            if h not in before:
                root.removeHandler(h)
                h.close()


class Sig:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *a):
        for fn in list(self.slots):
            fn(*a)


class World:
    """Alles, was main() von außen braucht, als Attrappen; so lässt sich der Ablauf ohne Fenster prüfen."""

    def __init__(self, monkeypatch, tmp_path, *, lock=True, pending=(), settings=None):
        self.cards, self.warnings, self.windows, self.installers, self.errors = [], [], [], [], []
        w = self
        w.quit_called = 0
        w.unlocked = 0
        w.update_checks = 0
        w.splash = None

        class QApp:
            def __init__(self, _argv):
                self.aboutToQuit = Sig()

            def setApplicationName(self, _n): ...
            def setStyleSheet(self, _s): ...
            def setFont(self, _f): ...
            def setWindowIcon(self, _i): ...
            def exec(self):
                w.splash.ready.emit() if w.splash.autostart else None
                return 7

            def quit(self):
                w.quit_called += 1

        class SplashStub:
            autostart = True

            def __init__(self, _steps):
                self.ready, self.failed, self.skipped, self.aborted = Sig(), Sig(), Sig(), Sig()
                self.progress = []
                self.dismissed = 0
                w.splash = self

            def show(self): ...
            def start(self): ...
            def dismiss(self):
                self.dismissed += 1

            def show_skip(self, _v): ...
            def show_progress(self, pct, text):
                self.progress.append((pct, text))

        class WindowStub:
            def __init__(self, _settings):
                w.windows.append(self)

            def show(self): ...

        class InstallerStub:
            def __init__(self, comps):
                self.comps, self.cancelled, self.started = comps, 0, 0
                self.progress, self.one_done, self.done = Sig(), Sig(), Sig()
                self.wait_ok = True
                w.installers.append(self)

            def start(self):
                self.started = 1

            def cancel(self):
                self.cancelled += 1

            def wait(self, _ms):
                return self.wait_ok

            def terminate(self):
                self.terminated = True

        class Card:
            def __init__(self, _w, kind, _title, text, **kw):
                w.cards.append((kind, text, kw))

            def run(self):
                return None

        monkeypatch.setattr(app, "QApplication", QApp)
        monkeypatch.setattr(app, "Splash", SplashStub)
        monkeypatch.setattr(app, "MainWindow", WindowStub)
        monkeypatch.setattr(app, "BootInstaller", InstallerStub)
        monkeypatch.setattr(app, "MessageCard", Card)
        monkeypatch.setattr(app.QMessageBox, "warning", staticmethod(lambda _p, _t, text: w.warnings.append(text)))
        monkeypatch.setattr(app, "pending_components", lambda: list(pending))
        monkeypatch.setattr(app, "load_settings", lambda: dict(settings or {"language": "de"}))
        monkeypatch.setattr(app, "start_update_check", lambda *_a: setattr(w, "update_checks", w.update_checks + 1))
        monkeypatch.setattr(app, "show_error", lambda _p, data: w.errors.append(data))
        monkeypatch.setattr(app, "data_dir", lambda: tmp_path / "data")
        monkeypatch.setattr(app, "acquire", lambda _p: SimpleNamespace(unlock=lambda: setattr(w, "unlocked", 1)) if lock else None)
        for name in ("brand_all", "install_cards", "install_error_logging", "log_startup", "_setup_logging", "set_lang",
                     "use_default_anchor"):
            monkeypatch.setattr(app, name, lambda *a, **k: None)
        monkeypatch.setattr(app, "load_icon", lambda: None)
        monkeypatch.setattr(app.fsutil, "harden", lambda: None)
        monkeypatch.setattr(app.dohfallback, "install_if_needed", lambda: "stub")
        import claudios.core.crashlog as crashlog
        monkeypatch.setattr(crashlog, "install", lambda *a, **k: True)


def test_a_second_instance_tells_the_user_and_exits_without_a_window(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, lock=False)
    assert app.main() == 0 and w.cards and w.cards[0][0] == "info" and w.windows == [] and w.splash is None


def test_a_normal_start_opens_one_window_checks_for_updates_and_releases_the_lock(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    assert app.main() == 7
    assert len(w.windows) == 1 and w.splash.dismissed == 1 and w.update_checks == 1 and w.unlocked == 1
    assert w.warnings == [] and w.installers == []
    w.splash.ready.emit()  # ein zweites Signal öffnet kein zweites Fenster
    assert len(w.windows) == 1


def test_warnings_for_a_broken_audit_log_and_missing_doh_are_shown_after_the_window_opens(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "startup_steps", lambda state: state.update(audit_ok=False, doh_ok=False) or [])
    app.main()
    assert len(w.warnings) == 2


def test_a_failing_start_step_is_shown_and_quits(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path)
    monkeypatch.setattr(app.QApplication, "exec", lambda self: (w.splash.failed.emit(RuntimeError("Schritt kaputt")), 1)[1])
    assert app.main() == 1 and w.windows == [] and len(w.errors) == 1 and w.quit_called == 1


def comp(name):
    return SimpleNamespace(name=name, title=name.upper())


def test_missing_components_are_installed_with_progress_and_failures_are_listed(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, pending=[comp("zap"), comp("node")])
    monkeypatch.setattr(app, "error_info", lambda exc: {"code": "E-1", "title": str(exc)})
    monkeypatch.setattr(app, "open_logs", lambda: None)
    holder = {}
    monkeypatch.setattr(app.QApplication, "exec", lambda self: holder.setdefault("app", self) and (w.splash.ready.emit(), 0)[1])
    app.main()
    installer = w.installers[0]
    assert installer.started == 1 and w.windows == [] and w.splash.progress[0][0] == 0
    installer.progress.emit("zap", "download", 1, 2)
    installer.one_done.emit("zap", None)
    installer.one_done.emit("node", ClaudiosError(E.INSTALL_CANCELLED))
    installer.done.emit([("zap", None), ("node", RuntimeError("kaputt"))])
    assert len(w.windows) == 1 and w.cards and w.cards[-1][0] == "warning" and "NODE" in w.cards[-1][1]
    holder["app"].aboutToQuit.slots[0]()  # beim Beenden werden die Installer gestoppt
    assert installer.cancelled >= 1


def test_skipping_the_installation_opens_the_window_and_stops_the_installer(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, pending=[comp("zap")])
    app.main()
    w.splash.skipped.emit()
    assert w.installers[0].cancelled == 1 and len(w.windows) == 1


def test_auto_install_off_never_installs_and_a_stuck_installer_is_terminated_on_quit(monkeypatch, tmp_path):
    w = World(monkeypatch, tmp_path, pending=[comp("zap")], settings={"auto_install": False})
    app.main()
    assert w.installers == [] and len(w.windows) == 1
    w2 = World(monkeypatch, tmp_path, pending=[comp("zap")])
    holder = {}
    monkeypatch.setattr(app.QApplication, "exec", lambda self: holder.setdefault("app", self) and (w2.splash.ready.emit(), 0)[1])
    app.main()
    w2.installers[0].wait_ok = False
    holder["app"].aboutToQuit.slots[0]()
    assert getattr(w2.installers[0], "terminated", False)
