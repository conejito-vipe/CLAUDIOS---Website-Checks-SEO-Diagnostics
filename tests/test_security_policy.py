import ast
import re
from pathlib import Path

import claudios
from claudios.core.redact import SECRET_PATTERNS

SRC = Path(claudios.__file__).parent
ROOT = SRC.parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

# Modul -> Dateien in src/claudios, die es importieren dürfen. Alles andere ist ein Befund und braucht eine Entscheidung.
ALLOWED_IMPORTS = {
    "subprocess": {"toolrunner.py", "piptools.py", "probe_zap.py"},
    "socket": {"tlsprobe.py", "probe_zap.py"},
    "ssl": {"net.py", "tlsprobe.py", "dohfallback.py"},
    "ctypes": {"credstore.py"},
    "http.server": {"oauth.py"},
    "dns.query": {"guard.py", "dohfallback.py"},
    "pickle": set(), "marshal": set(), "shelve": set(), "yaml": set(), "telnetlib": set(), "ftplib": set(),
    "smtplib": set(), "urllib.request": set(), "requests": set(),
}
SCAN_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".js", ".mjs", ".iss", ".toml", ".txt", ".cfg"}
SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "tests",
              "dist", "build"}
FORBIDDEN_FILES = ("client_secret*.json", "token*.json", "*.pem", "*.key", "*.pfx", ".env")


def imported_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def uses(names: set[str], module: str) -> bool:
    return any(name == module or name.startswith(module + ".") for name in names)


def repo_files():
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and not any(p in SKIP_PARTS or p.endswith(".egg-info") for p in parts):
            yield path


def test_risky_modules_are_imported_only_where_intended():
    found = {module: set() for module in ALLOWED_IMPORTS}
    for path in SRC.rglob("*.py"):
        names = imported_names(path)
        for module in ALLOWED_IMPORTS:
            if uses(names, module):
                found[module].add(path.name)
    unexpected = {m: sorted(files - ALLOWED_IMPORTS[m]) for m, files in found.items() if files - ALLOWED_IMPORTS[m]}
    assert unexpected == {}, f"nicht erlaubte Importe (Datei auf die Liste setzen oder entfernen): {unexpected}"


def test_no_dynamic_code_execution_or_os_command_helpers():
    calls = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                calls.append(f"{path.name}:{node.lineno}")
    assert calls == []
    text = "\n".join(p.read_text("utf-8") for p in SRC.rglob("*.py"))
    assert not re.search(r"os\.(popen|spawn\w*|exec\w*)\(", text)
    assert not re.search(r"dns\.query\.(udp|tcp|tls)\(", text)  # DNS nur über DoH


def test_every_workflow_declares_permissions_and_avoids_dangerous_triggers():
    assert WORKFLOWS
    for path in WORKFLOWS:
        text = path.read_text("utf-8")
        assert re.search(r"^permissions:", text, re.M), f"{path.name}: permissions fehlt"
        assert "pull_request_target" not in text, path.name
        assert not re.search(r"\$\{\{\s*github\.(event|head_ref)", text), f"{path.name}: Ereignisdaten in der Shell"
        assert not re.search(r"\|\s*(sudo\s+)?(ba)?sh\b", text), f"{path.name}: Download wird direkt ausgeführt"


def test_only_actions_from_github_itself_are_used():
    for path in WORKFLOWS:
        owners = re.findall(r"^\s*(?:-\s*)?uses:\s*([^/\s@]+)/", path.read_text("utf-8"), re.M)
        assert set(owners) <= {"actions"}, f"{path.name}: fremde Aktion {sorted(set(owners) - {'actions'})}"


def test_workflows_with_write_access_can_only_be_started_by_hand():
    for path in WORKFLOWS:
        text = path.read_text("utf-8")
        if "contents: write" in text:
            assert "workflow_dispatch" in text, path.name
            assert not re.search(r"^\s+(push|pull_request|schedule):", text, re.M), path.name


def test_no_secrets_in_the_repository():
    hits = []
    for path in repo_files():
        if path.suffix not in SCAN_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text("utf-8", errors="replace")
        hits += [f"{path.relative_to(ROOT).as_posix()}: {name}" for name, pat in SECRET_PATTERNS.items()
                 if pat.search(text)]
    assert hits == []


def test_no_credential_files_in_the_repository():
    names = [p.relative_to(ROOT).as_posix() for p in repo_files() if any(p.match(g) for g in FORBIDDEN_FILES)]
    assert names == []
