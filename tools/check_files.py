"""Prüft das ganze Projekt (Stand: Pakete 1 bis 6n): fehlende, leere, abgeschnittene oder doppelt eingefügte Dateien,
verirrte Dateien außerhalb des Pakets, Importe auf nicht vorhandene Module, alte Fassungen, fehlende Prüfsummen und
verbotene Texte. Spätere Pakete legen ihre Pflichtdateien in tools/manifests/*.txt ab (ein Pfad pro Zeile, Zeilen mit
# werden ignoriert), damit diese Datei nicht mehr geändert werden muss. Läuft in GitHub Actions ohne Konsole und in
tests/test_repo_layout.py. Der Aufruf meldet immer Exit-Code 0, damit der Autofix-Workflow weiterläuft; Funde stehen als
Annotations im Lauf."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = "src/claudios/"
PACKAGES = {"core", "checks", "components", "gsc", "i18n", "report", "ui"}


def files(prefix: str, suffix: str, names: str) -> list[str]:
    return [f"{prefix}{name}{suffix}" for name in names.split()]


REQUIRED: list[tuple[str, list[str]]] = [
    ("Hauptordner", ["pyproject.toml", "LICENSE", ".gitignore", "README.md", "README.de.md", "SECURITY.md",
                     "THREAT_MODEL.md", "FAQ.md", "CONTRIBUTING.md", "CHANGELOG.md", "CODE_OF_CONDUCT.md",
                     "THIRD_PARTY_NOTICES.md", "assets/ASSETS.md", "assets/logo-full.png", "docs/GOOGLE_SETUP.md",
                     "installer/launcher.py", "installer/claudios.iss"]),
    ("Werkzeuge", files("tools/", ".py", "count_loc update_lock check_files make_sbom find_duplicates")),
    ("GitHub", [".github/dependabot.yml", ".github/pull_request_template.md",
                ".github/ISSUE_TEMPLATE/bug_report.yml"]
     + files(".github/workflows/", ".yml",
             "ci autofix update-lock npm-lock pip-lock pw-lock zap-try build-windows security cleanup-scan")),
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
                                      "test_hardening test_hostile_input test_i18n test_notices test_npmchecks "
                                      "test_policy test_privacy_seo test_repo_layout test_retire_path "
                                      "test_sbom test_security_policy test_setup_highlight test_ssl test_tools "
                                      "test_zap")),
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
    (SRC + "core/limits.py", "sslyze_timeout_seconds"), (SRC + "core/limits.py", "gsc_inspections: int = 10 "),
    (SRC + "core/probes.py", "_extension_steps"), (SRC + "core/probes.py", "probe_tls"),
    (SRC + "core/engine.py", "gather_probes(gk, snap, doh, progress)"),
    (SRC + "core/errors.py", "GOOGLE_PROPERTY"), (SRC + "core/toolrunner.py", "extra_env"),
    (SRC + "core/redact.py", "{10,300}+"), (SRC + "core/seoprobe.py", "_locs"),
    (SRC + "checks/__init__.py", "pkgutil"), (SRC + "checks/_util.py", "group_digits"),
    (SRC + "checks/hardening.py", "(?<![A-Za-z0-9._%+-])"), (SRC + "checks/sslchecks.py", 'TARGET_FORMAT = "{host}:443'),
    (SRC + "checks/npmchecks.py", "_retire_rel"),
    (SRC + "i18n/__init__.py", "pkgutil"), (SRC + "i18n/strings.py", "probe.sitemap"),
    (SRC + "components/lock.py", "_extras"), (SRC + "components/manager.py", "_handler"),
    (SRC + "components/piptools.py", "--no-binary"), (SRC + "components/npm/package.json", '"retire": "^6'),
    (SRC + "ui/main_window.py", "_discover_pages"), (SRC + "ui/main_window.py", "nav_keys"),
    (SRC + "ui/pages.py", "scan.probe"), (SRC + "ui/worker.py", "scan_overrides"),
    ("pyproject.toml", "components/npm"), (".github/workflows/ci.yml", "QT_QPA_PLATFORM"),
    (".gitignore", "client_secret"), ("README.de.md", "assets/logo-full.png"),
    ("README.md", "assets/logo-full.png"), ("README.md", "README.de.md"), ("README.de.md", "README.md"),
    ("THIRD_PARTY_NOTICES.md", "Playwright"),
    ("THREAT_MODEL.md", "Residual risks"), ("THREAT_MODEL.de.md", "Restrisiken"),
    ("tests/test_privacy_seo.py", "BASE_STEPS"),
    ("tests/test_active_paths.py", "probe_zap"), ("tests/test_components.py", 'names[-1] == "npm-tools"'),
    ("tests/test_notices.py", "Chromium"),
]

# (Datei, Text, der NICHT darin stehen darf)
FORBIDDEN = [
    (SRC + "i18n/strings.py", "Nicht mit Anthropic"), (SRC + "i18n/strings.py", "Not affiliated with Anthropic"),
    ("README.de.md", "nicht mit Anthropic verbunden"), ("README.md", "not affiliated with Anthropic"),
    (SRC + "core/limits.py", "zap_timeout_seconds"),
]

Finding = tuple[str, str, str]  # (Stufe, Titel, Meldung)


def py_files(root: Path, folder: str) -> list[Path]:
    base = root / folder
    return sorted(base.rglob("*.py")) if base.is_dir() else []


def stray_files(root: Path = ROOT) -> list[str]:
    """Python-Dateien außerhalb von src/claudios/ (in src/ oder direkt im Hauptordner)."""
    out = [p.relative_to(root).as_posix() for p in py_files(root, "src")
           if not p.relative_to(root).as_posix().startswith("src/claudios/")]
    out += [p.name for p in sorted(root.glob("*.py"))]
    return out


def folders_without_init(root: Path = ROOT) -> list[str]:
    folders = {p.parent for p in py_files(root, "src/claudios")}
    return [f.relative_to(root).as_posix() for f in sorted(folders) if not (f / "__init__.py").is_file()]


def unknown_package_folders(root: Path = ROOT) -> list[str]:
    base = root / "src" / "claudios"
    folders = {p.parent for p in py_files(root, "src/claudios")} - {base}
    return [f.relative_to(root).as_posix() for f in sorted(folders)
            if f.relative_to(base).parts[0] not in PACKAGES or len(f.relative_to(base).parts) > 1]


def _exists(root: Path, parts: list[str]) -> bool:
    path = (root / "src" / "claudios").joinpath(*parts)
    return (path / "__init__.py").is_file() or (bool(parts) and path.with_suffix(".py").is_file())


def _is_package(root: Path, parts: list[str]) -> bool:
    return ((root / "src" / "claudios").joinpath(*parts) / "__init__.py").is_file()


def _defined_in_init(root: Path, parts: list[str], name: str) -> bool:
    try:
        return name in ((root / "src" / "claudios").joinpath(*parts) / "__init__.py").read_text("utf-8")
    except OSError:
        return False


def unresolved_imports(root: Path = ROOT) -> list[str]:
    """Importe auf Module von claudios, die es nicht gibt (nur Modulpfade; Namen nur bei Paketen)."""
    out: list[str] = []
    targets = [(p, True) for p in py_files(root, "src/claudios")] + [(p, False) for p in py_files(root, "tests")]
    for path, inside in targets:
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text("utf-8", errors="replace"))
        except SyntaxError:
            continue  # meldet die Syntaxprüfung
        package = list(path.relative_to(root / "src").with_suffix("").parts[1:-1]) if inside else []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] == "claudios" and not _exists(root, parts[1:]):
                        out.append(f"{rel}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if not node.module or node.module.split(".")[0] != "claudios":
                        continue
                    base = node.module.split(".")[1:]
                elif inside:
                    keep = len(package) - (node.level - 1)
                    if keep < 0:
                        out.append(f"{rel}:{node.lineno} Import verlässt das Paket")
                        continue
                    base = package[:keep] + (node.module.split(".") if node.module else [])
                else:
                    continue
                label = f"from {'.' * node.level}{node.module or ''}"
                if not _exists(root, base):
                    out.append(f"{rel}:{node.lineno} {label} import ...")
                elif _is_package(root, base):
                    for alias in node.names:
                        if alias.name != "*" and not _exists(root, base + [alias.name]) \
                                and not _defined_in_init(root, base, alias.name):
                            out.append(f"{rel}:{node.lineno} {label} import {alias.name}")
    return out


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text("utf-8", errors="replace")


def _check_python(root: Path, found: list[Finding]) -> None:
    for folder in ("src", "tests", "tools", "installer"):
        for path in py_files(root, folder):
            rel = path.relative_to(root).as_posix()
            text = path.read_text("utf-8", errors="replace")
            if path.name != "__init__.py" and not text.strip():
                found.append(("error", "Datei leer", rel))
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                found.append(("error", "Python-Syntax (abgeschnitten?)", f"{rel} Zeile {exc.lineno}"))
                continue
            seen: set[str] = set()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name in seen:
                        found.append(("warning", "Doppelt definiert (doppelt eingefügt?)", f"{rel}: {node.name}"))
                    seen.add(node.name)


def _check_json_and_checksums(root: Path, found: list[Finding]) -> None:
    for folder in (SRC + "i18n", SRC + "components"):
        base = root / folder
        for path in sorted(base.rglob("*.json")) if base.is_dir() else []:
            try:
                json.loads(path.read_text("utf-8"))
            except ValueError as exc:
                found.append(("error", "JSON unlesbar", f"{path.relative_to(root).as_posix()}: {exc}"))
    lock = root / SRC / "components" / "components.lock.json"
    if lock.is_file():
        try:
            items = json.loads(lock.read_text("utf-8")).get("components", [])
        except ValueError:
            items = []
        for item in items:
            if not item.get("sha256") or not str(item.get("url", "")).startswith("https://"):
                found.append(("warning", "Nicht gepinnt",
                              f"{item.get('name')}: Workflow 'Werkzeug-Prüfsummen eintragen' starten"))
    for rel, needle, workflow in GENERATED:
        path = root / rel
        if not path.is_file():
            found.append(("warning", "Sperrdatei fehlt", f"{rel}: Workflow '{workflow}' starten"))
        elif needle not in path.read_text("utf-8", errors="replace"):
            found.append(("warning", "Sperrdatei ohne Prüfsummen", f"{rel}: Workflow '{workflow}' starten"))


def collect(root: Path = ROOT) -> tuple[int, list[Finding]]:
    found: list[Finding] = []
    groups = list(REQUIRED)
    manifests = root / "tools" / "manifests"
    for manifest in sorted(manifests.glob("*.txt")) if manifests.is_dir() else []:
        lines = [x.strip() for x in manifest.read_text("utf-8").splitlines() if x.strip() and not x.startswith("#")]
        groups.append((f"Manifest {manifest.name}", lines))
    total = 0
    for label, group in groups:
        for rel in group:
            total += 1
            if not (root / rel).is_file():
                found.append(("error", f"Datei fehlt ({label})", rel))
    for rel, needle in CONTENT:
        if (root / rel).is_file() and needle not in _read(root, rel):
            found.append(("error", "Datei noch alt?", f"{rel} enthält nicht: {needle}"))
    for rel, needle in FORBIDDEN:
        if (root / rel).is_file() and needle in _read(root, rel):
            found.append(("error", "Verbotener Text", f"{rel} enthält noch: {needle}"))
    found += [("error", "Verirrte Datei (liegt außerhalb von src/claudios)", rel) for rel in stray_files(root)]
    found += [("error", "Ordner ohne __init__.py", rel) for rel in folders_without_init(root)]
    found += [("warning", "Unbekannter Paketordner", rel) for rel in unknown_package_folders(root)]
    found += [("error", "Import auf nicht vorhandenes Modul", rel) for rel in unresolved_imports(root)]
    _check_python(root, found)
    _check_json_and_checksums(root, found)
    return total, found


def main() -> int:
    total, found = collect()
    for level, title, message in found:
        print(f"::{level} title={title}::{message}")
        print(f"{level.upper():8}[{title}] {message}")
    errors = sum(1 for level, _title, _message in found if level == "error")
    print(f"\n{total} Pflichtdateien geprüft. " + (f"{errors} Fehler gefunden." if errors else "Keine Fehler."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
