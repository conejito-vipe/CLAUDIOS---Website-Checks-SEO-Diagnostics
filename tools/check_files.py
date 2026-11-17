"""Prüft das ganze Projekt (Stand: Ende der Entwicklung, Pakete 1 bis 5e): fehlende, leere, abgeschnittene oder doppelt
eingefügte Dateien, alte Fassungen, fehlende Prüfsummen und verbotene Texte. Läuft in GitHub Actions, ohne Konsole.
Meldet immer Exit-Code 0, damit der Autofix-Workflow weiterläuft; Funde stehen als Annotations im Lauf."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = "src/claudios/"


def files(prefix: str, suffix: str, names: str) -> list[str]:
    return [f"{prefix}{name}{suffix}" for name in names.split()]


REQUIRED: list[tuple[str, list[str]]] = [
    ("Hauptordner", ["pyproject.toml", "LICENSE", ".gitignore", "README.de.md", "README.en.md", "SECURITY.md",
                     "FAQ.md", "CONTRIBUTING.md", "CHANGELOG.md", "CODE_OF_CONDUCT.md", "THIRD_PARTY_NOTICES.md",
                     "assets/ASSETS.md", "assets/logo-full.png", "docs/GOOGLE_SETUP.md",
                     "installer/launcher.py", "installer/claudios.iss"]),
    ("Werkzeuge", files("tools/", ".py", "count_loc update_lock check_files")),
    ("GitHub", [".github/dependabot.yml", ".github/pull_request_template.md",
                ".github/ISSUE_TEMPLATE/bug_report.yml"]
     + files(".github/workflows/", ".yml", "ci autofix update-lock npm-lock pip-lock pw-lock zap-try build-windows")),
    ("Programm", files(SRC, ".py", "__init__ __main__ app buildinfo docs paths settings")),
    ("core", files(SRC + "core/", ".py",
                   "__init__ adsprobe assetprobe audit_log crawler dnsprobe engine errors findings guard limits "
                   "linkprobe net numfmt probe_gsc probe_paths probe_zap probes quota redact registry scoring "
                   "seoprobe snapshot takeoverprobe tlsprobe toolrunner")),
    ("checks", files(SRC + "checks/", ".py",
                     "__init__ _browser _util activechecks ads browserchecks codequality dns gscchecks hardening "
                     "html_checks links npmchecks privacy security seo seo_more sslchecks system takeover tls "
                     "tools_html zapchecks")),
    ("components", files(SRC + "components/", ".py",
                         "__init__ extra_playwright extra_sslyze lock manager npmtools piptools playwrighttools")
     + [SRC + "components/components.lock.json"]
     + files(SRC + "components/npm/", "", "package.json eslint.config.mjs stylelint.config.json pw-package.json "
                                          "browser_probe.js zap_probe.js")),
    ("gsc", files(SRC + "gsc/", ".py", "__init__ api credstore csvimport oauth session")),
    ("i18n", files(SRC + "i18n/", ".py", "__init__ strings strings_active strings_components strings_gsc "
                                        "strings_setup strings_tools strings_zap")
     + files(SRC + "i18n/", ".json", "errors errors_components errors_extra")),
    ("report", files(SRC + "report/", ".py", "__init__ report")),
    ("ui", files(SRC + "ui/", ".py", "__init__ components_page dialogs highlight main_window page_gsc page_setup "
                                    "pages splash theme widgets worker")),
    ("tests", files("tests/", ".py", "conftest test_active_paths test_browser test_checks_and_report "
                                     "test_components test_core test_crawler test_dns_links test_gsc test_gui "
                                     "test_hardening test_i18n test_notices test_npmchecks test_policy "
                                     "test_privacy_seo test_setup_highlight test_ssl test_tools test_zap")),
]

# Von Workflows erzeugte Dateien: (Pfad, Text, der darin stehen muss, Workflow)
GENERATED = [
    (SRC + "components/npm/package-lock.json", "node_modules/", "npm-Sperrdatei erzeugen"),
    (SRC + "components/npm/pw-package-lock.json", "node_modules/", "Playwright-Sperrdatei erzeugen"),
    (SRC + "components/pip-sslyze.json", "--hash=sha256:", "pip-Sperrliste für sslyze erzeugen"),
]

# (Datei, Text, der in der finalen Fassung stehen muss)
CONTENT = [
    (SRC + "core/limits.py", "takeover_hosts_max"), (SRC + "core/limits.py", "sitemap_urls_checked"),
    (SRC + "core/limits.py", "assets_css_max"), (SRC + "core/limits.py", "browser_timeout_seconds"),
    (SRC + "core/limits.py", "sslyze_timeout_seconds"),
    (SRC + "core/probes.py", "_extension_steps"), (SRC + "core/probes.py", "probe_tls"),
    (SRC + "core/engine.py", "gather_probes(gk, snap, doh, progress)"),
    (SRC + "core/errors.py", "GOOGLE_PROPERTY"), (SRC + "core/toolrunner.py", "extra_env"),
    (SRC + "checks/__init__.py", "pkgutil"), (SRC + "checks/_util.py", "group_digits"),
    (SRC + "checks/sslchecks.py", "TARGET_FORMAT"),
    (SRC + "i18n/__init__.py", "pkgutil"), (SRC + "i18n/strings.py", "probe.sitemap"),
    (SRC + "components/lock.py", "_extras"), (SRC + "components/manager.py", "_handler"),
    (SRC + "components/piptools.py", "--no-binary"),
    (SRC + "ui/main_window.py", "_discover_pages"), (SRC + "ui/main_window.py", "nav_keys"),
    (SRC + "ui/pages.py", "scan.probe"), (SRC + "ui/worker.py", "scan_overrides"),
    ("pyproject.toml", "components/npm"), (".github/workflows/ci.yml", "QT_QPA_PLATFORM"),
    (".gitignore", "client_secret"), ("README.de.md", "assets/logo-full.png"),
    ("README.en.md", "assets/logo-full.png"), ("THIRD_PARTY_NOTICES.md", "Playwright"),
    ("tests/test_privacy_seo.py", "BASE_STEPS"), ("tests/test_active_paths.py", "probe_zap"),
    ("tests/test_components.py", 'names[-1] == "npm-tools"'), ("tests/test_notices.py", "Chromium"),
]

# (Datei, Text, der NICHT darin stehen darf)
FORBIDDEN = [
    (SRC + "i18n/strings.py", "Nicht mit Anthropic"), (SRC + "i18n/strings.py", "Not affiliated with Anthropic"),
    ("README.de.md", "nicht mit Anthropic verbunden"), ("README.en.md", "not affiliated with Anthropic"),
]

problems = 0


def report(level: str, title: str, message: str) -> None:
    global problems
    if level == "error":
        problems += 1
    print(f"::{level} title={title}::{message}")
    print(f"{level.upper():8}[{title}] {message}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text("utf-8", errors="replace")


def check_python() -> None:
    for folder in ("src", "tests", "tools", "installer"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text("utf-8", errors="replace")
            if path.name != "__init__.py" and not text.strip():
                report("error", "Datei leer", rel)
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                report("error", "Python-Syntax (abgeschnitten?)", f"{rel} Zeile {exc.lineno}")
                continue
            seen: set[str] = set()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name in seen:
                        report("warning", "Doppelt definiert (doppelt eingefügt?)", f"{rel}: {node.name}")
                    seen.add(node.name)


def check_json() -> None:
    for folder in (SRC + "i18n", SRC + "components"):
        for path in sorted((ROOT / folder).rglob("*.json")):
            try:
                json.loads(path.read_text("utf-8"))
            except ValueError as exc:
                report("error", "JSON unlesbar", f"{path.relative_to(ROOT).as_posix()}: {exc}")


def check_checksums() -> None:
    lock = ROOT / SRC / "components" / "components.lock.json"
    if lock.is_file():
        try:
            items = json.loads(lock.read_text("utf-8")).get("components", [])
        except ValueError:
            return
        for item in items:
            if not item.get("sha256") or not str(item.get("url", "")).startswith("https://"):
                report("warning", "Nicht gepinnt", f"{item.get('name')}: Workflow 'Werkzeug-Prüfsummen eintragen' starten")
    for rel, needle, workflow in GENERATED:
        path = ROOT / rel
        if not path.is_file():
            report("warning", "Sperrdatei fehlt", f"{rel}: Workflow '{workflow}' starten")
        elif needle not in path.read_text("utf-8", errors="replace"):
            report("warning", "Sperrdatei ohne Prüfsummen", f"{rel}: Workflow '{workflow}' starten")


def main() -> int:
    total = 0
    for label, group in REQUIRED:
        for rel in group:
            total += 1
            if not (ROOT / rel).is_file():
                report("error", f"Datei fehlt ({label})", rel)
    for rel, needle in CONTENT:
        if (ROOT / rel).is_file() and needle not in read(rel):
            report("error", "Datei noch alt?", f"{rel} enthält nicht: {needle}")
    for rel, needle in FORBIDDEN:
        if (ROOT / rel).is_file() and needle in read(rel):
            report("error", "Verbotener Text", f"{rel} enthält noch: {needle}")
    check_python()
    check_json()
    check_checksums()
    print(f"\n{total} Pflichtdateien geprüft. " + (f"{problems} Fehler gefunden." if problems else "Keine Fehler."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
