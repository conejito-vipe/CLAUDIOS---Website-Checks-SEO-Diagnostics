"""Prüfungen mit Node-Werkzeugen (ESLint mit Security-Plugin, Stylelint, retire.js).
Sie bekommen nur Dateien aus dem Snapshot, nie eine Adresse. Fehlt ein Werkzeug oder ist die Ausgabe
unlesbar, gilt die Prüfung als nicht ausgeführt, nie als bestanden."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .. import paths
from ..components.manager import tool_path
from ..components.npmtools import node_env
from ..core.errors import ClaudiosError
from ..core.registry import check
from ..core.toolrunner import run_tool
from ._util import CheckSkipped, F, S
from .codequality import _assets, _css_sources, _js_sources

MAX_FILES = 40
TIMEOUT = 180.0
_ESLINT_WARN = {"security/detect-eval-with-expression", "security/detect-unsafe-regex"}
_STYLE_WARN = {"color-no-invalid-hex", "property-no-unknown", "unit-no-unknown"}
_RETIRE = {"critical": S.CRITICAL, "high": S.ERROR, "medium": S.WARNING, "low": S.NOTE}
_RETIRE_FALLBACK = "node_modules/retire/bin/retire"


def _node() -> Path:
    node = tool_path("node")
    if node is None:
        raise CheckSkipped("tool_not_found")
    return node


def _script(rel: str) -> Path:
    path = paths.tools_dir() / "npm-tools" / rel
    if not path.is_file():
        raise CheckSkipped("tool_not_found")
    return path


def _retire_rel() -> str:
    """Einstiegsdatei von retire.js laut dessen package.json (Feld 'bin'); der Dateiname ändert sich zwischen Versionen."""
    package = paths.tools_dir() / "npm-tools" / "node_modules" / "retire" / "package.json"
    try:
        entry = json.loads(package.read_text("utf-8")).get("bin")
    except (OSError, ValueError, AttributeError):
        entry = None
    if isinstance(entry, dict):
        entry = entry.get("retire")
    if isinstance(entry, str) and entry:
        parts = entry.replace("\\", "/").split("/")
        if not entry.startswith("/") and ".." not in parts:
            return "node_modules/retire/" + entry.replace("\\", "/").removeprefix("./")
    return _RETIRE_FALLBACK


def _run(args: list, cwd: str):
    try:
        return run_tool(args, cwd=cwd, timeout=TIMEOUT, extra_env=node_env(Path(args[0]).parent))
    except ClaudiosError:
        raise CheckSkipped("tool_failed") from None


def _write(folder, items: list[tuple[str, str]], suffix: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for index, (url, body) in enumerate(items[:MAX_FILES]):
        name = f"f{index}{suffix}"
        (Path(folder) / name).write_text(body, "utf-8")
        names[name] = url
    return names


def _load(text: str):
    try:
        return json.loads(text)
    except ValueError:
        raise CheckSkipped("tool_output_unreadable") from None


def _base(path: str) -> str:
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def _collect(entries, names: dict, fallback: str, rule_key: str, text_key: str):
    """Fasst Meldungen je Regel zusammen. Gibt (Regeln, Dateien ohne Analyse) zurück."""
    rules: dict[str, dict] = {}
    unparsable: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = names.get(_base(entry.get("filePath") or entry.get("source") or ""), fallback)
        for msg in entry.get("messages") or entry.get("warnings") or []:
            if not isinstance(msg, dict):
                continue
            rule = msg.get(rule_key)
            if msg.get("fatal") or not rule or rule == "CssSyntaxError":
                if url not in unparsable:
                    unparsable.append(url)
                continue
            rec = rules.setdefault(rule, {"count": 0, "url": url, "first": f"Line {msg.get('line')}: {msg.get(text_key)}"})
            rec["count"] += 1
    return rules, unparsable


@check("JSS-ESL-001",
       title="JavaScript-Analyse mit ESLint (Security-Plugin) ## JavaScript analysis with ESLint (security plugin)",
       why="ESLint mit dem Security-Plugin findet Muster, die zu Sicherheitslücken führen können, etwa unsichere "
           "reguläre Ausdrücke, dynamisch erzeugte Prozessaufrufe oder eval mit Ausdrücken. Das ergänzt die "
           "einfache Textsuche um eine echte Syntaxanalyse. ## ESLint with the security plugin finds patterns "
           "that can lead to vulnerabilities, such as unsafe regular expressions, dynamically built process "
           "calls or eval with expressions. This complements the plain text search with a real syntax analysis.",
       method="Schreibt die abgerufenen eigenen Skripte und die Inline-Skripte (höchstens 40 Dateien) in einen "
              "Zwischenordner und startet ESLint mit eigener Konfiguration (eslint-plugin-security, ohne die "
              "sehr unscharfe Regel detect-object-injection) über das portable Node. Skripte in Modul-Syntax "
              "oder mit Fehlern werden nur als Info gemeldet. Bei fehlendem Werkzeug oder unlesbarer Ausgabe gilt "
              "die Prüfung als nicht ausgeführt. ## Writes the fetched own scripts and the inline scripts (at "
              "most 40 files) to a temporary folder and starts ESLint with its own configuration "
              "(eslint-plugin-security, without the very imprecise rule detect-object-injection) using the "
              "portable Node. Scripts in module syntax or with errors are only reported as info. With a missing "
              "tool or unreadable output the check counts as not executed.",
       logic="detect-eval-with-expression und detect-unsafe-regex: Warnung. Andere Sicherheitsregeln: Hinweis. "
             "Nicht analysierbares Skript: Info. ## detect-eval-with-expression and detect-unsafe-regex: warning. "
             "Other security rules: note. Script that cannot be analysed: info.",
       fix="Die im Beleg genannte Stelle prüfen und durch eine sichere Alternative ersetzen (feste Ausdrücke, "
           "keine dynamisch gebauten Befehle). ## Check the place named in the evidence and replace it with a safe "
           "alternative (fixed expressions, no dynamically built commands).",
       refs=["https://eslint.org/docs/latest/", "https://github.com/eslint-community/eslint-plugin-security"],
       profiles="sd", source="tool", needs=("node", "npm-tools"))
def eslint(snap):
    items = _js_sources(snap, _assets(snap))
    if not items:
        return []
    node, script, config = _node(), _script("node_modules/eslint/bin/eslint.js"), _script("eslint.config.mjs")
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        names = _write(tmp, items, ".js")
        result = _run([node, script, "-c", config, "--no-warn-ignored", "--format", "json", *names], tmp)
    if result.returncode not in (0, 1):
        raise CheckSkipped("tool_failed")
    data = _load(result.stdout)
    if not isinstance(data, list):
        raise CheckSkipped("tool_output_unreadable")
    rules, unparsable = _collect(data, names, snap.target.url, "ruleId", "message")
    out = []
    for rule, rec in sorted(rules.items()):
        severity = S.WARNING if rule in _ESLINT_WARN else S.NOTE
        out.append(F("JSS-ESL-001", severity, rec["url"],
                     f"Auffällige JavaScript-Stelle laut ESLint ({rule}, {rec['count']}x)",
                     f"Suspicious JavaScript spot reported by ESLint ({rule}, {rec['count']}x)", rec["first"]))
    for url in unparsable:
        out.append(F("JSS-ESL-001", S.INFO, url, "Skript konnte von ESLint nicht analysiert werden",
                     "Script could not be analysed by ESLint"))
    return out


@check("CSS-STY-001",
       title="CSS-Qualität mit Stylelint ## CSS quality with Stylelint",
       why="Stylelint findet Fehler, die der Browser stillschweigend hinnimmt: unbekannte Eigenschaften und "
           "Einheiten, ungültige Farben, doppelte Selektoren oder Eigenschaften und überschriebene Regeln. Sie "
           "verursachen unerwartete Darstellung und machen Änderungen schwer. ## Stylelint finds errors that "
           "the browser silently accepts: unknown properties and units, invalid colours, duplicate selectors "
           "or properties and overridden rules. They cause unexpected rendering and make changes hard.",
       method="Schreibt die abgerufenen eigenen Stylesheets und die style-Elemente (höchstens 40 Dateien) in "
              "einen Zwischenordner und startet Stylelint mit einer kleinen eigenen Regelliste über das portable "
              "Node. Bei fehlendem Werkzeug, fehlerhafter Konfiguration oder unlesbarer Ausgabe gilt die Prüfung "
              "als nicht ausgeführt. ## Writes the fetched own stylesheets and the style elements (at most 40 "
              "files) to a temporary folder and starts Stylelint with a small own rule list using the portable "
              "Node. With a missing tool, faulty configuration or unreadable output the check counts as not "
              "executed.",
       logic="Ungültige Farbe, unbekannte Eigenschaft oder Einheit: Warnung. Andere Regeln: Hinweis. "
             "Nicht analysierbare Datei: Info. ## Invalid colour, unknown property or unit: warning. Other "
             "rules: note. File that cannot be analysed: info.",
       fix="Die im Beleg genannte Regel korrigieren; Dubletten zusammenführen. ## Fix the rule named in the "
           "evidence; merge duplicates.",
       refs=["https://stylelint.io/", "https://developer.mozilla.org/en-US/docs/Web/CSS/Reference"],
       profiles="sd", source="tool", needs=("node", "npm-tools"))
def stylelint(snap):
    items = _css_sources(snap, _assets(snap))
    if not items:
        return []
    node = _node()
    script, config = _script("node_modules/stylelint/bin/stylelint.mjs"), _script("stylelint.config.json")
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        names = _write(tmp, items, ".css")
        out_file = Path(tmp) / "result.json"
        result = _run([node, script, "--config", config, "--formatter", "json", "--output-file", out_file,
                       *names], tmp)
        if result.returncode not in (0, 2):
            raise CheckSkipped("tool_failed")
        try:
            text = out_file.read_text("utf-8")
        except OSError:
            raise CheckSkipped("tool_output_unreadable") from None
    data = _load(text)
    if not isinstance(data, list):
        raise CheckSkipped("tool_output_unreadable")
    if any(isinstance(e, dict) and e.get("invalidOptionWarnings") for e in data):
        raise CheckSkipped("tool_failed")
    rules, unparsable = _collect(data, names, snap.target.url, "rule", "text")
    out = []
    for rule, rec in sorted(rules.items()):
        severity = S.WARNING if rule in _STYLE_WARN else S.NOTE
        out.append(F("CSS-STY-001", severity, rec["url"], f"CSS-Regelverstoß laut Stylelint ({rule}, {rec['count']}x)",
                     f"CSS rule violation reported by Stylelint ({rule}, {rec['count']}x)", rec["first"]))
    for url in unparsable:
        out.append(F("CSS-STY-001", S.INFO, url, "Stylesheet konnte von Stylelint nicht analysiert werden",
                     "Stylesheet could not be analysed by Stylelint"))
    return out


@check("JSS-RET-001",
       title="Veraltete JavaScript-Bibliotheken (retire.js) ## Outdated JavaScript libraries (retire.js)",
       why="Alte Versionen von Bibliotheken wie jQuery oder Bootstrap haben oft bekannte Sicherheitslücken, die "
           "Angreifer automatisiert ausnutzen. Eine Prüfung gegen eine Schwachstellenliste zeigt, welche "
           "Bibliothek dringend aktualisiert werden muss. ## Old versions of libraries such as jQuery or "
           "Bootstrap often have known vulnerabilities that attackers exploit automatically. A check against a "
           "vulnerability list shows which library urgently needs updating.",
       method="Schreibt die abgerufenen eigenen Skripte (höchstens 40 Dateien) in einen Zwischenordner und startet "
              "retire.js darauf. retire.js lädt dabei seine Schwachstellenliste von raw.githubusercontent.com (nur "
              "HTTPS, nicht von der geprüften Website). Bibliotheken, die von fremden Servern (CDN) geladen werden, "
              "werden nicht erkannt, weil diese Dateien nicht abgerufen werden. Bei fehlendem Werkzeug, "
              "Fehlschlag oder unlesbarer Ausgabe gilt die Prüfung als nicht ausgeführt. ## Writes the fetched "
              "own scripts (at most 40 files) to a temporary folder and starts retire.js on them. retire.js "
              "downloads its vulnerability list from raw.githubusercontent.com (HTTPS only, not from the checked "
              "website). Libraries loaded from foreign servers (CDN) are not detected because those files are "
              "not fetched. With a missing tool, a failure or unreadable output the check counts as not "
              "executed.",
       logic="Je Bibliothek nach der schwersten Lücke: kritisch, hoch: Fehler, mittel: Warnung, niedrig: Hinweis. ## "
             "Per library by the most severe vulnerability: critical: critical, high: error, medium: warning, "
             "low: note.",
       fix="Die Bibliothek auf die aktuelle Version aktualisieren oder entfernen. ## Update the library to the "
           "current version or remove it.",
       refs=["https://retirejs.github.io/retire.js/", "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/"],
       profiles="sd", source="tool", needs=("node", "npm-tools"))
def retire(snap):
    items = _js_sources(snap, _assets(snap))
    if not items:
        return []
    node, script = _node(), _script(_retire_rel())
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        scan = Path(tmp) / "scan"
        scan.mkdir()
        names = _write(scan, items, ".js")
        out_file = Path(tmp) / "retire.json"
        result = _run([node, script, "--path", scan, "--outputformat", "json", "--outputpath", out_file,
                       "--exitwith", "0"], tmp)
        if result.returncode != 0:
            raise CheckSkipped("tool_failed")
        try:
            text = out_file.read_text("utf-8")
        except OSError:
            raise CheckSkipped("tool_output_unreadable") from None
    data = _load(text)
    entries = data.get("data") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise CheckSkipped("tool_output_unreadable")
    found: dict[tuple[str, str], dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = names.get(_base(entry.get("file", "")), snap.target.url)
        for res in entry.get("results") or []:
            vulns = [v for v in (res.get("vulnerabilities") or []) if isinstance(v, dict)]
            if not vulns:
                continue
            key = (str(res.get("component")), str(res.get("version")))
            rec = found.setdefault(key, {"url": url, "severity": S.NOTE, "count": 0, "cve": ""})
            for vuln in vulns:
                rec["count"] += 1
                rec["severity"] = max(rec["severity"], _RETIRE.get(str(vuln.get("severity")).lower(), S.NOTE))
                cves = (vuln.get("identifiers") or {}).get("CVE") or []
                if cves and not rec["cve"]:
                    rec["cve"] = str(cves[0])
    out = []
    for (component, version), rec in sorted(found.items()):
        out.append(F("JSS-RET-001", rec["severity"], rec["url"],
                     f"{component} {version} hat {rec['count']} bekannte Schwachstelle(n)",
                     f"{component} {version} has {rec['count']} known vulnerability(ies)", rec["cve"]))
    return out
