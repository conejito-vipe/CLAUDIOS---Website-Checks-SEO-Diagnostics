"""Praxisprüfung der npm-Werkzeuge auf dem GitHub-Rechner (nicht im Programm): startet ESLint, Stylelint und retire.js
mit den Konfigurationen und den Aufrufen von checks/npmchecks.py. Modus 'pinned': die Versionen aus der Sperrdatei
(npm ci). Modus 'latest': ESLint, Stylelint und eslint-plugin-security in der neuesten Version (npm install im
Zwischenordner, die Sperrdatei im Repository bleibt unberührt). Ergebnisse stehen als Annotationen im Lauf. Der Aufruf
meldet immer Exit-Code 0."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "src" / "claudios" / "components"
NPM = COMP / "npm"
JQUERY = "https://code.jquery.com/jquery-1.6.1.min.js"
SAMPLE_JS = "const input = process.argv[2];\neval(input);\nnew RegExp(input);\nconsole.log(1);\n"
SAMPLE_CSS = "a { color: #ggg; }\n"
UPGRADE = ("eslint@latest", "stylelint@latest", "eslint-plugin-security@latest")
COPY = ("package.json", "package-lock.json", "eslint.config.mjs", "stylelint.config.json")


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:700]}")


def run(cmd: list, cwd: Path, timeout: float = 600.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, errors="replace",
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", type(exc).__name__
    return proc.returncode, proc.stdout, proc.stderr


def bin_of(package: dict, name: str) -> str | None:
    """Einstiegsdatei aus dem Feld 'bin' (relativ, ohne '..'), wie checks/npmchecks.py sie bestimmt."""
    entry = package.get("bin")
    if isinstance(entry, dict):
        entry = entry.get(name)
    if not isinstance(entry, str) or not entry:
        return None
    cleaned = entry.replace("\\", "/")
    if cleaned.startswith("/") or ".." in cleaned.split("/"):
        return None
    return cleaned.removeprefix("./")


def read_package(work: Path, name: str) -> dict:
    try:
        data = json.loads((work / "node_modules" / name / "package.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def eslint_summary(data) -> tuple[bool, str]:
    if not isinstance(data, list):
        return False, "Ausgabe ist keine Liste"
    rules = sorted({str(m.get("ruleId")) for f in data if isinstance(f, dict)
                    for m in f.get("messages") or [] if isinstance(m, dict)})
    return any(r.startswith("security/") for r in rules), f"Regeln: {rules}"


def stylelint_summary(data) -> tuple[bool, str]:
    if not isinstance(data, list):
        return False, "Ausgabe ist keine Liste"
    items = [f for f in data if isinstance(f, dict)]
    rules = sorted({str(w.get("rule")) for f in items for w in f.get("warnings") or [] if isinstance(w, dict)})
    invalid = sum(len(f.get("invalidOptionWarnings") or []) for f in items)
    return "color-no-invalid-hex" in rules and invalid == 0, f"Regeln: {rules}, ungültige Optionen: {invalid}"


def retire_summary(data) -> tuple[bool, str]:
    entries = data.get("data") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return False, "Ausgabe hat kein Feld data"
    found = sorted({str(r.get("component")) for d in entries if isinstance(d, dict)
                    for r in d.get("results") or [] if isinstance(r, dict) and r.get("vulnerabilities")})
    return "jquery" in found, f"Bibliotheken mit Lücken: {found}"


def claudios_node_version() -> str:
    try:
        items = json.loads((COMP / "components.lock.json").read_text("utf-8")).get("components", [])
    except (OSError, ValueError):
        return "?"
    return next((str(i.get("version")) for i in items if i.get("name") == "node"), "?")


def load_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def verdict(ok: bool, title: str, message: str) -> None:
    note("notice" if ok else "error", title, message)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pinned"
    npm, node = shutil.which("npm"), shutil.which("node")
    if not npm or not node:
        note("error", "npm-Werkzeuge", "node oder npm nicht gefunden")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name in COPY:
            shutil.copy2(NPM / name, work / name)
        base = ["--ignore-scripts", "--no-audit", "--no-fund"]
        cmd = [npm, "install", *UPGRADE, *base] if mode == "latest" else [npm, "ci", *base]
        code, out, err = run(cmd, work)
        verdict(code == 0, f"Installation ({mode})", f"Exit {code}. {(out + err)[-300:]}")
        if code != 0:
            return 0
        pkgs = {name: read_package(work, name) for name in ("eslint", "stylelint", "retire", "eslint-plugin-security")}
        note("notice", f"Versionen ({mode})", ", ".join(f"{n} {p.get('version')}" for n, p in pkgs.items()))
        note("notice", f"Node-Anforderung ({mode})", "; ".join(
            f"{n}: {p.get('engines', {}).get('node', '-')}" for n, p in pkgs.items() if n != "retire"))
        _code, version, _err = run([node, "--version"], work)
        note("notice", "Node-Version", f"Runner {version.strip()}, von Claudios installiert {claudios_node_version()}")
        (work / "f0.js").write_text(SAMPLE_JS, "utf-8")
        (work / "f1.css").write_text(SAMPLE_CSS, "utf-8")
        scan = work / "scan"
        scan.mkdir()
        (scan / "f0.js").write_text(SAMPLE_JS, "utf-8")
        try:
            with urllib.request.urlopen(JQUERY, timeout=60) as resp:
                (scan / "jquery-1.6.1.min.js").write_bytes(resp.read(2_000_000))
        except Exception as exc:  # noqa: BLE001
            note("warning", "jquery-Probe", f"nicht geladen ({type(exc).__name__}): retire kann nichts finden")
        rel = {n: bin_of(pkgs[n], n) for n in ("eslint", "stylelint", "retire")}
        note("notice", f"Einstiegsdateien ({mode})", str(rel))
        if rel["eslint"]:
            code, out, err = run([node, work / "node_modules" / "eslint" / rel["eslint"], "-c", "eslint.config.mjs",
                                  "--no-warn-ignored", "--format", "json", "f0.js"], work)
            try:
                ok, text = eslint_summary(json.loads(out))
            except ValueError:
                ok, text = False, f"keine JSON-Ausgabe: {(out + err)[:200]}"
            verdict(ok and code in (0, 1), f"ESLint ({mode})", f"Exit {code}. {text}")
        if rel["stylelint"]:
            target = work / "result.json"
            code, out, err = run([node, work / "node_modules" / "stylelint" / rel["stylelint"], "--config",
                                  "stylelint.config.json", "--formatter", "json", "--output-file", target,
                                  "f1.css"], work)
            ok, text = stylelint_summary(load_json(target))
            verdict(ok and code in (0, 2), f"Stylelint ({mode})", f"Exit {code}. {text}. stderr: {err[:120]}")
        if rel["retire"]:
            target = work / "retire.json"
            code, out, err = run([node, work / "node_modules" / "retire" / rel["retire"], "--path", scan,
                                  "--outputformat", "json", "--outputpath", target, "--exitwith", "0"], work)
            ok, text = retire_summary(load_json(target))
            verdict(ok and code == 0, f"retire.js ({mode})", f"Exit {code}. {text}. stderr: {err[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
