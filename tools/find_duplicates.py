"""Meldet doppelte Codeblöcke (mindestens 6 Zeilen), gleiche Funktionsnamen in mehreren Dateien und private Namen, die
über Dateigrenzen importiert werden. Nur Lesen, ändert nichts. Aufruf: python tools/find_duplicates.py"""
from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 6
MIN_CHARS = 120  # Mindestlänge eines Fensters, damit Zeilen wie "return out" nicht zählen
SKIP_NAMES = {"main", "create", "collect", "status", "install", "retranslate", "refresh", "run", "page", "make_snap",
              "env", "fetch", "fake"}


def _normalize(line: str) -> str:
    return re.sub(r"\s+", " ", line.split("#", 1)[0]).strip()


def code_lines(path: Path) -> list[tuple[int, str]]:
    out = []
    for number, line in enumerate(path.read_text("utf-8", errors="replace").splitlines(), 1):
        text = _normalize(line)
        if text and not text.startswith(("import ", "from ", '"""', "'''")) and text not in "()[]{}":
            out.append((number, text))
    return out


def duplicate_blocks(folder: str) -> list[str]:
    files: dict[str, list[tuple[int, str]]] = {}
    windows: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path in sorted((ROOT / folder).rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = code_lines(path)
        for i in range(len(files[rel]) - WINDOW + 1):
            key = "\n".join(text for _n, text in files[rel][i:i + WINDOW])
            if len(key) >= MIN_CHARS:
                windows[key].append((rel, i))
    hits: dict[str, dict[int, tuple[str, int]]] = defaultdict(dict)
    for locations in windows.values():
        for rel, i in locations:
            other = next(((r, j) for r, j in locations if (r, j) != (rel, i) and (r != rel or abs(j - i) >= WINDOW)),
                         None)
            if other:
                hits[rel][i] = other
    found: list[tuple[int, str]] = []
    for rel, indexes in sorted(hits.items()):
        run: dict | None = None
        for i in sorted(indexes) + [-10]:
            other = indexes.get(i)
            if run and other and i == run["end"] + 1 and other[0] == run["other"][0]:
                run["end"] = i
                continue
            if run:
                first, last = files[rel][run["start"]][0], files[rel][run["end"] + WINDOW - 1][0]
                o_rel, o_idx = run["other"]
                size = run["end"] - run["start"] + WINDOW
                found.append((size, f"{rel}:{first}-{last} ({size} Zeilen) wie {o_rel}:{files[o_rel][o_idx][0]}"))
            run = {"start": i, "end": i, "other": other} if other else None
    return [text for _size, text in sorted(found, reverse=True)]


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
    return [f"{name}: {', '.join(files)}" for name, files in sorted(where.items())
            if len(files) > 1 and name not in SKIP_NAMES and not name.startswith("test_")]


def private_imports() -> list[str]:
    """Private Namen (mit Unterstrich), die aus anderen Modulen importiert werden."""
    out = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8", errors="replace"))):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                for alias in node.names:
                    if alias.name.startswith("_") and not alias.name.startswith("__"):
                        out.append(f"{path.relative_to(ROOT).as_posix()}: {alias.name} aus "
                                   f"{'.' * node.level}{node.module or ''}")
    return out


def main() -> int:
    groups = {
        "Doppelte Blöcke (src)": duplicate_blocks("src"),
        "Doppelte Blöcke (tests)": duplicate_blocks("tests"),
        "Gleiche Namen in mehreren Dateien (src)": duplicate_functions("src"),
        "Gleiche Namen in mehreren Dateien (tests)": duplicate_functions("tests"),
        "Private Namen über Dateigrenzen": private_imports(),
    }
    for title, items in groups.items():
        print(f"== {title}: {len(items)}")
        for item in items:
            print("  " + item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
