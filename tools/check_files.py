"""Prüft, ob alle Dateien der Pakete 1 bis 4c-1 vorhanden und aktuell sind (läuft in GitHub Actions, ohne Konsole)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = "src/claudios/"

BASE = [
    "pyproject.toml", "LICENSE", ".gitignore", ".github/workflows/ci.yml", "tools/count_loc.py",
    SRC + "__init__.py", SRC + "__main__.py", SRC + "app.py", SRC + "buildinfo.py", SRC + "docs.py",
    SRC + "paths.py", SRC + "settings.py",
]
for name in ("__init__", "adsprobe", "audit_log", "crawler", "dnsprobe", "engine", "errors", "findings", "guard",
             "limits", "linkprobe", "net", "numfmt", "probes", "quota", "redact", "registry", "scoring",
             "seoprobe", "snapshot", "takeoverprobe"):
    BASE.append(f"{SRC}core/{name}.py")
for name in ("__init__", "_util", "ads", "dns", "hardening", "html_checks", "links", "privacy", "security",
             "seo", "seo_more", "system", "takeover"):
    BASE.append(f"{SRC}checks/{name}.py")
for name in ("__init__.py", "errors.json", "strings.py"):
    BASE.append(f"{SRC}i18n/{name}")
for name in ("__init__", "report"):
    BASE.append(f"{SRC}report/{name}.py")
for name in ("__init__", "dialogs", "main_window", "pages", "splash", "theme", "widgets", "worker"):
    BASE.append(f"{SRC}ui/{name}.py")
for name in ("conftest", "test_checks_and_report", "test_core", "test_crawler", "test_dns_links", "test_gui",
             "test_hardening", "test_i18n", "test_policy", "test_privacy_seo"):
    BASE.append(f"tests/{name}.py")

P4A = [SRC + "components/__init__.py", SRC + "components/components.lock.json", SRC + "components/lock.py",
       SRC + "components/manager.py", SRC + "i18n/errors_components.json", SRC + "i18n/strings_components.py",
       SRC + "ui/components_page.py", "tools/update_lock.py", "tests/test_components.py"]
P4B = [SRC + "core/toolrunner.py", SRC + "core/assetprobe.py", SRC + "core/tlsprobe.py",
       SRC + "checks/tools_html.py", SRC + "checks/codequality.py", SRC + "checks/tls.py",
       SRC + "i18n/strings_tools.py", "tests/test_tools.py"]
P4C1 = [SRC + "components/npmtools.py", SRC + "components/npm/package.json",
        SRC + "components/npm/eslint.config.mjs", SRC + "components/npm/stylelint.config.json",
        SRC + "checks/npmchecks.py", SRC + "i18n/errors_extra.json", "tests/test_npmchecks.py",
        ".github/workflows/npm-lock.yml"]

# (Datei, Text, der in der neuen Fassung stehen muss, Paket)
CONTENT = [
    (SRC + "core/limits.py", "takeover_hosts_max", "3b-1"), (SRC + "core/limits.py", "sitemap_urls_checked", "3b-2"),
    (SRC + "core/limits.py", "assets_css_max", "4b"), (SRC + "core/limits.py", "browser_timeout_seconds", "Struktur"),
    (SRC + "core/probes.py", "collect_sitemap", "3b-2"), (SRC + "core/probes.py", "probe_tls", "4b"),
    (SRC + "core/engine.py", "gather_probes(gk, snap, doh, progress)", "3b-2"),
    (SRC + "checks/_util.py", "group_digits", "3b-2"),
    (SRC + "checks/__init__.py", "pkgutil", "Struktur"), (SRC + "i18n/__init__.py", "pkgutil", "Struktur"),
    (SRC + "core/errors.py", "GOOGLE_PROPERTY", "Struktur"),
    (SRC + "components/lock.py", "_extras", "Struktur"), (SRC + "components/manager.py", "_handler", "Struktur"),
    (SRC + "ui/main_window.py", "_discover_pages", "Struktur"),
    (SRC + "ui/worker.py", "component_checker", "4b"), (SRC + "ui/pages.py", "scan.probe", "3b-2"),
    (SRC + "i18n/strings.py", "probe.sitemap", "3b-2"), (SRC + "ui/main_window.py", "ComponentsPage", "4a"),
    ("pyproject.toml", "components/npm", "4c-1"), ("tests/test_privacy_seo.py", "probe:tls", "4b"),
    ("tests/test_components.py", 'names[-1] == "npm-tools"', "Struktur"),
]


def main() -> int:
    problems = 0
    groups = ((BASE, "Pakete 1-3b"), (P4A, "Paket 4a"), (P4B, "Paket 4b"), (P4C1, "Paket 4c-1"))
    for group, label in groups:
        for rel in group:
            if not (ROOT / rel).is_file():
                problems += 1
                print(f"::error title=Datei fehlt ({label})::{rel}")
                print(f"FEHLT   [{label}] {rel}")
    for rel, needle, label in CONTENT:
        path = ROOT / rel
        if path.is_file() and needle not in path.read_text("utf-8"):
            problems += 1
            print(f"::error title=Datei noch alt? (Paket {label})::{rel} enthaelt nicht: {needle}")
            print(f"ALT?    [Paket {label}] {rel} enthaelt nicht: {needle}")
    print(f"\n{problems} Problem(e) gefunden." if problems else "\nAlle Dateien vorhanden und aktuell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
