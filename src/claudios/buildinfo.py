"""Zählt reine Python-Codezeilen für den Footer (ohne Leerzeilen, Kommentare, Docstrings)."""
from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    return lines


def count_code_lines(root: Path) -> int:
    total = 0
    for path in root.rglob("*.py"):
        text = path.read_text("utf-8")
        doc = _docstring_lines(ast.parse(text))
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped and number not in doc and not stripped.startswith("#"):
                total += 1
    return total


@lru_cache(maxsize=1)
def python_lines() -> int:
    """Aus dem Quellcode gezählt; in einem Build ohne .py-Dateien aus build_info.json."""
    root = Path(__file__).resolve().parent
    live = count_code_lines(root)
    if live > 0:
        return live
    try:
        return int(json.loads((root / "build_info.json").read_text("utf-8"))["code"])
    except (OSError, ValueError, KeyError):
        return 0
