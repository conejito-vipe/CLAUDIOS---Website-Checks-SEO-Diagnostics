"""Richtlinien-Tests: sichern die Sicherheitsvorgaben dauerhaft ab (laufen in der CI)."""
import re
from pathlib import Path

import claudios

SRC = Path(claudios.__file__).parent
ROOT = SRC.parent.parent
PY_FILES = list(SRC.rglob("*.py"))


def _scan(pattern, files=PY_FILES, skip=()):
    rx = re.compile(pattern)
    return [f"{p.name}:{n}" for p in files if p.name not in skip
            for n, line in enumerate(p.read_text("utf-8").splitlines(), 1) if rx.search(line)]


def test_no_disabled_certificate_verification():
    assert _scan(r"verify\s*=\s*False|ignoreHTTPSErrors|NODE_TLS_REJECT_UNAUTHORIZED|ignore-certificate-errors|CERT_NONE") == []


def test_no_hardcoded_insecure_urls():
    assert _scan(r"http://[A-Za-z0-9]") == []


def test_no_shell_execution():
    assert _scan(r"shell\s*=\s*True|os\.system\(") == []


def test_no_command_line_scan_interface():
    import tomllib

    assert _scan(r"^\s*(import argparse|from argparse|import click|import typer)") == []
    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert "scripts" not in data["project"] and "gui-scripts" not in data["project"]


def test_numbers_are_formatted_only_via_numfmt():
    assert _scan(r"\{[^}]*:,[^}]*\}", skip=("numfmt.py",)) == []


def test_no_old_name_left():
    old = "clau" + "dia"
    hits = [str(p.relative_to(ROOT)) for p in list(SRC.rglob("*.py")) + list(SRC.rglob("*.json"))
            if old in p.read_text("utf-8").lower()]
    assert hits == [], f"alter Name noch vorhanden in: {hits}"
