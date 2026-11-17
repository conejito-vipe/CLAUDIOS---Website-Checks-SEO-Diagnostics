"""Meldet doppelte Codeblöcke (mindestens 6 Zeilen) und doppelt definierte Hilfsfunktionen in src/ und tests/.
Nur Lesen, ändert nichts. Aufruf: python tools/find_duplicates.py"""
from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 6
MIN_CHARS = 40


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line.split("#", 1)[0]).strip()


def code_lines(path: Path) -> list[tuple[int, str]]:
    out = []
    for number, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
        text = _normalize(line)
        if text and not text.startswith(("import ", "from ", '"""', "'''")) and text not in ("(", ")", "[", "]", "{", "}"):
            out.append((number, text))
    return out


def duplicate_blocks(folder: str) -> list[str]:
    seen: dict[str, tuple[str, int]] = {}
    reported: set[tuple[str, int]] = set()
    results = []
    for path in sorted((ROOT / folder).rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        lines = code_lines(path)
        for i in range(len(lines) - WINDOW + 1):
            chunk = lines[i:i + WINDOW]
            key = "\n".join(text for _n, text in chunk)
            if len(key) < MIN_CHARS * WINDOW // 2:
                continue
            start = (rel, chunk[0][0])
            if key in seen and seen[key][0] != rel or (key in seen and seen[key][1] != chunk[0][0] and seen[key][0] == rel):
                first = seen[key]
                if start not in reported and first not in reported:
                    reported.add(start)
                    results.append(f"{rel}:{chunk[0][0]} wie {first[0]}:{first[1]}")
            else:
                seen.setdefault(key, start)
    return results


def duplicate_functions(folder: str) -> list[str]:
    where: dict[str, list[str]] = defaultdict(list)
    for path in sorted((ROOT / folder).rglob("*.py")):
        try:
            tree = ast.parse(path.read_text("utf-8", errors="replace"))
        except SyntaxError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                where[node.name].append(rel)
    skip = {"main", "create", "collect", "status", "install", "retranslate", "refresh", "run", "page", "make_snap", "env"}
    return [f"{name}: {', '.join(files)}" for name, files in sorted(where.items())
            if len(files) > 1 and name not in skip and not name.startswith("test_")]


def private_imports() -> list[str]:
    """Private Namen (mit Unterstrich), die aus anderen Modulen importiert werden."""
    out = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8", errors="replace"))):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                for alias in node.names:
                    if alias.name.startswith("_") and not alias.name.startswith("__"):
                        out.append(f"{path.relative_to(ROOT).as_posix()}: {alias.name} aus {'.' * node.level}{node.module or ''}")
    return out


def main() -> int:
    groups = {
        "Doppelte Blöcke (src)": duplicate_blocks("src"),
        "Doppelte Blöcke (tests)": duplicate_blocks("tests"),
        "Gleiche Funktionsnamen in mehreren Dateien (src)": duplicate_functions("src"),
        "Gleiche Funktionsnamen in mehreren Dateien (tests)": duplicate_functions("tests"),
        "Private Namen über Dateigrenzen": private_imports(),
    }
    for title, items in groups.items():
        print(f"== {title}: {len(items)}")
        for item in items:
            print("  " + item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
