"""Selbsttest des Programms (CLAUDIOS.exe --selftest): prüft im gebauten Programm, was Tests auf dem Entwicklungsrechner nicht sehen.
Geprüft werden: alle Module importierbar (fehlende PyInstaller-Bausteine), mitgelieferte Dateien, DNS über HTTPS, Prüfregister,
Schreibrechte im Datenordner, auf Windows ein echter Rundlauf durch die Anmeldedaten-Verwaltung und das Hauptfenster (gezeichnet).
Das Ergebnis ist ein JSON-Bericht (Pfad aus --selftest <Datei> oder der Umgebungsvariable CLAUDIOS_SELFTEST_OUT, sonst
logs/selftest.json im Datenordner). Der Bericht enthält keine Zugangsdaten und ersetzt den Benutzerordner durch "~".
Exit-Code 0 = alles in Ordnung, 1 = mindestens eine Prüfung ist fehlgeschlagen."""
from __future__ import annotations

import importlib
import json
import os
import pkgutil
import platform
import secrets
import sys
import tempfile
import time
from collections.abc import Callable
from importlib import resources
from pathlib import Path

from . import __version__

ENV_OUT = "CLAUDIOS_SELFTEST_OUT"
SKIP_MODULES = {"claudios.__main__", "claudios.selftest"}
SCRIPTS = ("browser_probe.js", "engine_probe.js", "shot_probe.js", "zap_probe.js")
LOCK_FILES = ("components.lock.json", "runtime-lock.json", "pip-sslyze.json", "sslyze-wheel.json")


def _mask(text: str) -> str:
    home = str(Path.home())
    return text.replace(home, "~") if home else text


def check_environment() -> str:
    return _mask(f"CLAUDIOS {__version__}, Python {platform.python_version()}, {platform.platform()}, "
                 f"frozen={bool(getattr(sys, 'frozen', False))}, exe={sys.executable}")


def check_modules() -> str:
    import claudios

    failed: list[str] = []
    total = 0
    for info in pkgutil.walk_packages(claudios.__path__, "claudios."):
        if info.name in SKIP_MODULES:
            continue
        total += 1
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler ist hier eine Auskunft
            failed.append(f"{info.name}: {type(exc).__name__}: {exc}")
    if total < 50:  # ein gebautes Programm mit zu wenigen Modulen ist unvollständig (oder die Suche versagt)
        failed.append(f"nur {total} Module gefunden")
    if failed:
        raise RuntimeError("; ".join(failed[:10]) + (f" (+{len(failed) - 10})" if len(failed) > 10 else ""))
    return f"{total} Module importiert"


def check_resources() -> str:
    missing = []
    components = resources.files("claudios.components")
    for name in LOCK_FILES:
        if not components.joinpath(name).is_file():
            missing.append(name)
    for name in SCRIPTS + ("package.json", "package-lock.json"):
        if not components.joinpath("npm").joinpath(name).is_file():
            missing.append("npm/" + name)
    from .paths import assets_dir

    folder = assets_dir()
    if folder is None or not any(folder.glob("*.png")):
        missing.append("assets/*.png")
    if missing:
        raise RuntimeError("fehlt: " + ", ".join(missing))
    return "Sperrdateien, Browser-Skripte und Bilder vorhanden"


def check_doh() -> str:
    from .core._frozen_imports import doh_status

    ok, detail = doh_status()
    if not ok:
        raise RuntimeError(detail)
    return detail or "DNS über HTTPS verfügbar"


def check_registry() -> str:
    from .checks import load_all
    from .core.errors import catalog
    from .core.registry import validate_registry

    load_all()
    errors = validate_registry()
    if errors:
        raise RuntimeError(errors[0])
    if not catalog():
        raise RuntimeError("Fehlerkatalog leer")
    return "Prüfregister und Fehlerkatalog in Ordnung"


def check_data_dir() -> str:
    from .paths import cache_dir

    folder = cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, delete=True) as handle:
        handle.write(b"ok")
    return "Datenordner beschreibbar"


def check_credential_store() -> str:
    if sys.platform not in ("win32", "darwin"):
        return "übersprungen (nur Windows und macOS)"
    from .gsc.credstore import MacStore, WindowsStore

    store = WindowsStore() if sys.platform == "win32" else MacStore()
    name = "CLAUDIOS-selftest-" + secrets.token_hex(4)
    text = "selftest-" + secrets.token_hex(8)
    try:
        store.write(name, text)
        if store.read(name) != text:
            raise RuntimeError("gelesener Wert weicht ab")
    finally:
        store.delete(name)
    if store.read(name) is not None:
        raise RuntimeError("Eintrag blieb nach dem Löschen bestehen")
    store.delete(name)  # Löschen eines fehlenden Eintrags ist kein Fehler
    return "Schreiben, Lesen, Löschen in der " + ("Windows-Anmeldedaten-Verwaltung" if sys.platform == "win32" else "Schlüsselbund von macOS")


def check_main_window() -> str:
    from PySide6.QtWidgets import QApplication

    from .i18n.brand import brand_all
    from .i18n.strings import TEXTS
    from .ui.main_window import MainWindow
    from .ui.theme import STYLE
    from .ui.theme_extra import EXTRA

    app = QApplication.instance() or QApplication(sys.argv[:1])
    brand_all(TEXTS)
    app.setStyleSheet(STYLE + EXTRA)
    window = MainWindow({"language": "de", "allow_localhost": False})
    try:
        window.resize(1100, 720)
        window.show()
        app.processEvents()
        image = window.grab().toImage()
        if image.isNull() or image.width() < 600:
            raise RuntimeError("Hauptfenster lässt sich nicht zeichnen")
        return f"Hauptfenster gezeichnet ({image.width()}x{image.height()}), {window.nav.count()} Seiten"
    finally:
        window.close()


CHECKS: tuple[tuple[str, Callable[[], str]], ...] = (
    ("environment", check_environment), ("modules", check_modules), ("resources", check_resources),
    ("doh", check_doh), ("registry", check_registry), ("data_dir", check_data_dir),
    ("credential_store", check_credential_store), ("main_window", check_main_window),
)


def run_checks(checks=CHECKS) -> dict:
    results = []
    for name, func in checks:
        started = time.monotonic()
        try:
            detail, ok = func(), True
        except Exception as exc:  # noqa: BLE001 – jede Prüfung meldet ihren Fehler, der Lauf geht weiter
            detail, ok = f"{type(exc).__name__}: {exc}", False
        results.append({"name": name, "ok": ok, "detail": _mask(str(detail))[:1500],
                        "ms": int((time.monotonic() - started) * 1000)})
    return {"ok": all(r["ok"] for r in results), "version": __version__, "checks": results}


def output_path(argv: list[str]) -> Path:
    if "--selftest" in argv:
        index = argv.index("--selftest")
        if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
            return Path(argv[index + 1])
    if os.environ.get(ENV_OUT):
        return Path(os.environ[ENV_OUT])
    from .paths import logs_dir

    return logs_dir() / "selftest.json"


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    report = run_checks()
    try:
        target = output_path(argv)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    except OSError as exc:
        report["ok"] = False
        report["checks"].append({"name": "report", "ok": False, "detail": f"Bericht nicht schreibbar: {exc}", "ms": 0})
    for entry in report["checks"]:
        print(("OK   " if entry["ok"] else "FEHL ") + f"{entry['name']}: {entry['detail']}")
    return 0 if report["ok"] else 1
