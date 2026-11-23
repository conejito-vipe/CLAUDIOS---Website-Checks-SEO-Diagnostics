"""Prüfungen mit externen W3C-Werkzeugen (Java). Sie bekommen nur Dateien aus dem Snapshot, nie eine Adresse.
Fehlt ein Werkzeug oder ist seine Ausgabe unlesbar, gilt die Prüfung als nicht ausgeführt, nie als bestanden."""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from .. import paths
from ..components.manager import tool_path
from ..core.errors import ClaudiosError
from ..core.limits import LIMITS
from ..core.registry import check
from ..core.toolrunner import run_tool
from ._util import CheckSkipped, F, S

log = logging.getLogger("claudios")


def _tools(*names: str) -> list[Path]:
    found = [tool_path(name) for name in names]
    if any(item is None for item in found):
        raise CheckSkipped("tool_not_found")
    return found


def _json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        raise CheckSkipped("tool_output_unreadable") from None


def _vnu_messages(result, files: int) -> list:
    """Meldungen aus der JSON-Ausgabe von vnu. Abgeschnittene oder unlesbare Ausgabe: nicht ausgeführt, mit Größe im Protokoll."""
    text = getattr(result, "stdout", "") or ""
    truncated = bool(getattr(result, "truncated", False))
    if truncated:
        log.info("vnu output truncated: %d bytes for %d files", len(text), files)
        raise CheckSkipped("tool_output_unreadable")
    try:
        data = _json(text)
    except CheckSkipped:
        log.info("vnu output is not JSON: %d bytes for %d files", len(text), files)
        raise
    found = data.get("messages") if isinstance(data, dict) else None
    if not isinstance(found, list):
        log.info("vnu output has no message list: %d bytes for %d files", len(text), files)
        raise CheckSkipped("tool_output_unreadable")
    return found


@check("HTM-VAL-001",
       title="HTML-Validierung (W3C Nu Html Checker) ## HTML validation (W3C Nu Html Checker)",
       why="Fehlerhaftes HTML (falsche Verschachtelung, ungültige Attribute, veraltete Elemente) wird von jedem "
           "Browser anders repariert. Das führt zu uneinheitlicher Darstellung, Problemen für Screenreader und "
           "schwer auffindbaren Fehlern. Der Nu Html Checker ist die Referenz des W3C. ## Faulty HTML (wrong "
           "nesting, invalid attributes, obsolete elements) is repaired differently by every browser. This "
           "leads to inconsistent rendering, problems for screen readers and hard-to-find bugs. The Nu Html "
           "Checker is the W3C reference.",
       method="Schreibt die gecrawlten HTML-Seiten (höchstens 25) in einen Zwischenordner und startet vnu.jar "
              "in Gruppen zu je 10 Dateien (java -jar vnu.jar --format json --stdout). Die Meldungen werden je Seite "
              "gezählt, die erste erscheint im Beleg. Bei fehlenden Werkzeugen oder unlesbarer Ausgabe gilt die "
              "Prüfung als nicht ausgeführt. ## Writes the crawled HTML pages (at most 25) to a temporary folder "
              "and starts vnu.jar in groups of 10 files (java -jar vnu.jar --format json --stdout). Messages are "
              "counted per page, the first one appears in the evidence. With missing tools or unreadable output "
              "the check counts as not executed.",
       logic="Fehler laut Validator: Fehler. Warnungen: Hinweis. ## Validator error: error. Warnings: note.",
       fix="Die im Beleg genannte Stelle korrigieren und die Seite erneut unter https://validator.w3.org/nu/ "
           "prüfen. ## Fix the place named in the evidence and check the page again at "
           "https://validator.w3.org/nu/.",
       refs=["https://validator.w3.org/nu/", "https://github.com/validator/validator",
             "https://html.spec.whatwg.org/multipage/"],
       profiles="sd", source="tool", needs=("java", "vnu"))
def html_validation(snap):
    docs = snap.docs()[: LIMITS.vnu_pages_max]
    if not docs:
        return []
    java, jar = _tools("java", "vnu")
    names: dict[str, object] = {}
    messages: list = []
    size = max(1, LIMITS.vnu_batch)
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        for start in range(0, len(docs), size):
            batch: dict[str, object] = {}
            for index in range(start, min(start + size, len(docs))):
                name = f"p{index}.html"
                (Path(tmp) / name).write_text(docs[index].html, "utf-8")
                batch[name] = docs[index]
            try:
                result = run_tool([java, "-Xss1024k", "-jar", jar, "--format", "json", "--stdout",
                                   "--skip-non-html", *batch], cwd=tmp)
            except ClaudiosError:
                raise CheckSkipped("tool_failed") from None
            part = _vnu_messages(result, len(batch))
            if any(m.get("type") == "non-document-error" for m in part if isinstance(m, dict)):
                raise CheckSkipped("tool_failed")
            names.update(batch)
            messages.extend(part)
    out = []
    for name, pg in names.items():
        mine = [m for m in messages if isinstance(m, dict) and str(m.get("url", "")).rsplit("/", 1)[-1] == name]
        errors = [m for m in mine if m.get("type") == "error"]
        warnings = [m for m in mine if m.get("type") == "info" and m.get("subType") == "warning"]
        if errors:
            first = errors[0]
            out.append(F("HTM-VAL-001", S.ERROR, pg.url, f"{len(errors)} HTML-Fehler laut W3C Nu Html Checker",
                         f"{len(errors)} HTML error(s) reported by the W3C Nu Html Checker",
                         f"Line {first.get('lastLine')}: {first.get('message')}"))
        if warnings:
            first = warnings[0]
            out.append(F("HTM-VAL-001", S.NOTE, pg.url, f"{len(warnings)} HTML-Warnung(en) laut W3C Nu Html Checker",
                         f"{len(warnings)} HTML warning(s) reported by the W3C Nu Html Checker",
                         f"Line {first.get('lastLine')}: {first.get('message')}"))
    return out


@check("CSS-VAL-001",
       title="CSS-Validierung (W3C CSS Validator) ## CSS validation (W3C CSS Validator)",
       why="Ungültige CSS-Regeln werden vom Browser stillschweigend verworfen. Die Darstellung weicht dann von "
           "der Absicht ab, und der Fehler fällt oft nur in einem Browser auf. ## Invalid CSS rules are silently "
           "discarded by the browser. The rendering then deviates from the intent, and the error often shows "
           "in only one browser.",
       method="Prüft bis zu 6 abgerufene Stylesheets der eigenen Domain einzeln mit dem W3C CSS Validator "
              "(java -jar css-validator.jar --output=json <Datei>). Inline-Stile und Fremd-Stylesheets werden nicht "
              "geprüft. Bei fehlenden Werkzeugen oder unlesbarer Ausgabe gilt die Prüfung als nicht ausgeführt. ## "
              "Checks up to 6 fetched stylesheets of the own domain one by one with the W3C CSS Validator "
              "(java -jar css-validator.jar --output=json <file>). Inline styles and third-party stylesheets are "
              "not checked. With missing tools or unreadable output the check counts as not executed.",
       logic="Fehler laut Validator: Fehler. Warnungen: Hinweis. ## Validator error: error. Warnings: note.",
       fix="Die im Beleg genannte Regel korrigieren und unter https://jigsaw.w3.org/css-validator/ erneut prüfen. ## "
           "Fix the rule named in the evidence and check again at https://jigsaw.w3.org/css-validator/.",
       refs=["https://jigsaw.w3.org/css-validator/", "https://github.com/w3c/css-validator",
             "https://www.w3.org/Style/CSS/"],
       profiles="sd", source="tool", needs=("java", "css-validator"))
def css_validation(snap):
    assets = snap.extra.get("assets")
    if assets is None:
        raise CheckSkipped("no_asset_data")
    files = [a for a in assets["css"] if a["status"] == 200 and a["text"]][: LIMITS.assets_css_max]
    if not files:
        return []
    java, jar = _tools("java", "css-validator")
    out = []
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        for index, asset in enumerate(files):
            target = Path(tmp) / f"c{index}.css"
            target.write_text(asset["text"], "utf-8")
            try:
                result = run_tool([java, "-jar", jar, "--output=json", target.as_uri()], cwd=tmp)
            except ClaudiosError:
                raise CheckSkipped("tool_failed") from None
            data = _json(result.stdout)
            section = data.get("cssvalidation") if isinstance(data, dict) else None
            if not isinstance(section, dict):
                raise CheckSkipped("tool_output_unreadable")
            errors = [m for m in section.get("errors") or [] if isinstance(m, dict)]
            warnings = [m for m in section.get("warnings") or [] if isinstance(m, dict)]
            if errors:
                out.append(F("CSS-VAL-001", S.ERROR, asset["url"], f"{len(errors)} CSS-Fehler laut W3C CSS Validator",
                             f"{len(errors)} CSS error(s) reported by the W3C CSS Validator",
                             f"Line {errors[0].get('line')}: {errors[0].get('message')}"))
            if warnings:
                out.append(F("CSS-VAL-001", S.NOTE, asset["url"],
                             f"{len(warnings)} CSS-Warnung(en) laut W3C CSS Validator",
                             f"{len(warnings)} CSS warning(s) reported by the W3C CSS Validator",
                             f"Line {warnings[0].get('line')}: {warnings[0].get('message')}"))
    return out