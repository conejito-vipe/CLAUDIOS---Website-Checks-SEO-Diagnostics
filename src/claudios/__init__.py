"""Zählt reine Python-Codezeilen (ohne Leerzeilen, Kommentare, Docstrings, Tests)."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "claudios"


def _docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    return lines


def count_file(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    doc_lines = _docstring_lines(ast.parse(text))
    res = {"code": 0, "blank": 0, "comment": 0, "docstring": 0}
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            res["blank"] += 1
        elif no in doc_lines:
            res["docstring"] += 1
        elif s.startswith("#"):
            res["comment"] += 1
        else:
            res["code"] += 1
    return res


def main() -> int:
    total = {"code": 0, "blank": 0, "comment": 0, "docstring": 0, "files": 0}
    for f in sorted(SRC.rglob("*.py")):
        for k, v in count_file(f).items():
            total[k] += v
        total["files"] += 1
    total["tests_lines"] = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in (ROOT / "tests").rglob("*.py"))
    (SRC / "build_info.json").write_text(json.dumps(total, indent=2), encoding="utf-8")
    print(json.dumps(total, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
