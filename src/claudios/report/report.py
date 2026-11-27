"""Bericht: JSON (echte Zahlen), HTML (strenge CSP, alles maskiert), ZIP mit Prompt. Keine Passwörter, nirgends.
Ein abgebrochener Scan zeigt keine Gesamtwertung (sie wäre irreführend)."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from ..checks import load_all
from ..core.engine import ScanResult
from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.limits import LIMITS
from ..core.names import check_title
from ..core.numfmt import format_bytes, format_number
from ..core.redact import find_leaks, redact_url, sanitize_obj
from ..core.registry import REGISTRY

CSS = ("body{font:14px/1.5 system-ui,sans-serif;background:#E9EEF2;color:#1b2a33;margin:2rem}"
       "h1{color:#EE6A12}table{border-collapse:collapse;width:100%;background:#fff}"
       "td,th{border:1px solid #cfd8de;padding:.4rem .6rem;text-align:left;vertical-align:top}"
       ".s4{background:#f8d7da}.s3{background:#fde2cf}.s2{background:#fff3cd}.s1,.s0{background:#fff}")
SEV = ["info", "note", "warning", "error", "critical"]


def group_findings(findings) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for f in findings:
        g = groups.setdefault((f.check_id, int(f.severity), f.msg_de, f.msg_en), {
            "check_id": f.check_id, "severity": int(f.severity), "severity_name": SEV[int(f.severity)],
            "msg_de": f.msg_de, "msg_en": f.msg_en, "count": 0, "example_urls": [], "evidence": f.evidence})
        g["count"] += 1
        if len(g["example_urls"]) < 5 and f.url not in g["example_urls"]:
            g["example_urls"].append(f.url)
    return sorted(groups.values(), key=lambda g: (-g["severity"], g["check_id"]))


def build_report(result: ScanResult, lang: str = "de") -> dict:
    load_all()
    s = result.snapshot
    rep = {
        "tool": {"name": "CLAUDIOS", "version": __version__},
        "number_format_note": "JSON numbers are plain numbers (no thousands separators).",
        "scan": {
            "target": redact_url(s.target.url), "level": s.level, "profile": s.profile, "status": s.status,
            "started": datetime.fromtimestamp(s.started, UTC).isoformat(),
            "finished": datetime.fromtimestamp(s.finished or s.started, UTC).isoformat(),
            "abort": s.abort, "pages_checked": len(s.pages), "requests": result.requests,
            "bytes": result.bytes_total, "skipped": s.skipped,
        },
        "limits": asdict(LIMITS),
        "scores": result.scores,
        "checks": [{"id": cid, "status": st,
                    "title_de": REGISTRY[cid].meta.title["de"], "title_en": REGISTRY[cid].meta.title["en"]}
                   for cid, st in sorted(result.executed.items()) if cid in REGISTRY],
        "findings": group_findings(result.findings),
        "pages": [{"url": redact_url(p.url), "status": p.status, "depth": p.depth, "elapsed_ms": p.elapsed_ms,
                   "bytes": p.size, "error": p.error} for p in s.pages],
    }
    return sanitize_obj(rep)  # Sanitizer: zweite Schicht nach der Schwärzung beim Einlesen


_T = {
    "de": {"title": "CLAUDIOS-Bericht", "score": "Gesamtwertung", "status": "Status", "sev": "Schwere",
           "check": "Prüfung", "cnt": "Anzahl", "msg": "Befund", "ex": "Beispiele", "pages": "Seiten geprüft",
           "bytes": "Daten", "notrun": "Nicht ausgeführt",
           "noscore": "keine (der Scan wurde abgebrochen)",
           "st": {"complete": "vollständig", "limited": "mit Einschränkungen", "aborted": "abgebrochen"},
           "disc": "Technische Indizien, keine Rechtsberatung. Orientierungswert, kein Gütesiegel."},
    "en": {"title": "CLAUDIOS report", "score": "Overall score", "status": "Status", "sev": "Severity",
           "check": "Check", "cnt": "Count", "msg": "Finding", "ex": "Examples", "pages": "Pages checked",
           "bytes": "Data", "notrun": "Not executed",
           "noscore": "none (the scan was aborted)",
           "st": {"complete": "complete", "limited": "with limitations", "aborted": "aborted"},
           "disc": "Technical indications, not legal advice. Orientation value, not a certification."},
}


def _aborted(rep: dict) -> bool:
    return rep["scan"]["status"] == "aborted"


def render_html(rep: dict, lang: str = "de") -> str:
    t, e = _T[lang], html.escape

    def n(v, d=0):
        return format_number(v, lang, d)

    sc = rep["scan"]
    css_hash = base64.b64encode(hashlib.sha256(CSS.encode()).digest()).decode()
    csp = f"default-src 'none'; style-src 'sha256-{css_hash}'; base-uri 'none'; form-action 'none'"
    rows = "".join(
        f'<tr class="s{g["severity"]}"><td>{e(g["severity_name"])}</td><td>{e(check_title(g["check_id"], lang))}</td>'
        f'<td>{n(g["count"])}</td><td>{e(g["msg_" + lang])}<br><small>{e(g["evidence"])}</small></td>'
        f'<td>{e(", ".join(g["example_urls"]))}</td></tr>' for g in rep["findings"])
    notrun = "".join(f"<li>{e(c['title_' + lang])} ({e(c['status'])})</li>"
                     for c in rep["checks"] if c["status"] != "ran")
    abort = ""
    if sc["abort"]:
        a = sc["abort"][lang]
        abort = f"<p><strong>{e(a['title'])}</strong> {e(a['cause'])} {e(a['action'])}</p>"
    if _aborted(rep):
        score = f'<p><strong>{t["score"]}: {e(t["noscore"])}</strong></p>'
    else:
        cats = ", ".join(f"{e(k)}: {n(v)}" for k, v in rep["scores"]["categories"].items())
        score = f'<p><strong>{t["score"]}: {n(rep["scores"]["overall"])}/100</strong> ({cats})</p>'
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{e(csp)}"><meta name="referrer" content="no-referrer">'
            f'<title>{t["title"]}</title><style>{CSS}</style></head><body><h1>{t["title"]}</h1>'
            f'<p>{e(sc["target"])} · {t["status"]}: {e(t["st"][sc["status"]])} · {t["pages"]}: {n(sc["pages_checked"])} · '
            f'{t["bytes"]}: {format_bytes(sc["bytes"], lang)}</p>{abort}{score}'
            f'<table><tr><th>{t["sev"]}</th><th>{t["check"]}</th><th>{t["cnt"]}</th><th>{t["msg"]}</th><th>{t["ex"]}</th></tr>'
            f'{rows}</table>' + (f'<h2>{t["notrun"]}</h2><ul>{notrun}</ul>' if notrun else "") +
            f'<p><small>{t["disc"]}</small></p></body></html>')


def render_summary(rep: dict, lang: str = "de") -> str:
    t = _T[lang]

    def n(v, d=0):
        return format_number(v, lang, d)

    sc = rep["scan"]
    score = t["noscore"] if _aborted(rep) else f"{n(rep['scores']['overall'])}/100"
    lines = [f"# {t['title']}: {sc['target']}", "",
             f"- {t['status']}: {t['st'][sc['status']]}", f"- {t['score']}: {score}",
             f"- {t['pages']}: {n(sc['pages_checked'])}", ""]
    if sc["abort"]:
        a = sc["abort"][lang]
        lines += [f"**{a['title']}**: {a['cause']} {a['action']}", ""]
    for g in rep["findings"][:15]:
        lines.append(f"- [{g['severity_name']}] {check_title(g['check_id'], lang)} ({n(g['count'])}x): {g['msg_' + lang]}")
    return "\n".join(lines) + "\n"


PROMPT = {
    "de": """# Auftrag an Claude
Anbei der Prüfbericht des Tools **CLAUDIOS** (Website-Checks) als ZIP. Bitte:

1. **Bewerte** den Gesamtzustand der Website (Sicherheit, HTML/CSS/JS-Sauberkeit, SEO, Datenschutz).
2. **Priorisiere** die Befunde (kritisch zuerst) und erkläre je Befund kurz, warum er wichtig ist.
3. Gib **konkrete Lösungsvorschläge mit Codebeispielen** (z. B. Header für nginx/Apache, HTML-Korrekturen).
4. Nenne mögliche **Fehlalarme** und was CLAUDIOS nicht prüfen konnte (siehe `checks[].status` und `scan.status`).
5. Fasse am Ende einen **Maßnahmenplan** (Quick Wins, mittelfristig) zusammen.

Hinweise: Die Berichte enthalten keine Passwörter, Cookie-Werte oder Tokens. Zahlen in `report.html` und `summary.md`
sind deutsch formatiert (**Punkt = Tausendertrenner**, Komma = Dezimal); in `report.json` stehen reine Zahlen.
Befunde sind technische Indizien, keine Rechtsberatung. Antworte auf Deutsch.
""",
    "en": """# Task for Claude
Attached is the report of the tool **CLAUDIOS** (website checks) as a ZIP. Please:

1. **Assess** the overall state of the website (security, HTML/CSS/JS cleanliness, SEO, privacy).
2. **Prioritise** the findings (critical first) and briefly explain why each matters.
3. Provide **concrete fixes with code examples** (e.g. headers for nginx/Apache, HTML corrections).
4. Point out possible **false positives** and what CLAUDIOS could not check (see `checks[].status` and `scan.status`).
5. Finish with an **action plan** (quick wins, medium term).

Notes: The reports contain no passwords, cookie values or tokens. Numbers in `report.html` and `summary.md` use
English formatting (**comma = thousands separator**, period = decimal); `report.json` contains plain numbers.
Findings are technical indications, not legal advice. Answer in English.
""",
}


def _files(result: ScanResult, lang: str) -> dict[str, str]:
    rep = build_report(result, lang)
    files = {"prompt.md": PROMPT[lang], "summary.md": render_summary(rep, lang),
             "report.json": json.dumps(rep, ensure_ascii=False, indent=2), "report.html": render_html(rep, lang)}
    for name, text in files.items():  # letzte Schranke: nichts Erkennbares darf mehr drin sein
        leaks = find_leaks(text)
        if leaks:
            raise ClaudiosError(E.EXPORT_FAILED, reason=f"possible secret in {name}: {leaks[0]}")
    return files


def zip_preview(result: ScanResult, lang: str = "de") -> list[tuple[str, int]]:
    """Für den Vorschau-Dialog: Dateiname und Größe in Bytes."""
    return [(k, len(v.encode())) for k, v in _files(result, lang).items()]


def build_zip(result: ScanResult, dest: Path | str, lang: str = "de") -> Path:
    dest = Path(dest)
    try:
        files = _files(result, lang)
        manifest = {
            "claudios_version": __version__, "created": datetime.now(UTC).isoformat(), "language": lang,
            "files": {k: {"sha256": hashlib.sha256(v.encode()).hexdigest(), "bytes": len(v.encode())}
                      for k, v in files.items()},
            "limits": asdict(LIMITS), "contains_secrets": False,
        }
        files["manifest.json"] = json.dumps(manifest, indent=2)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for name, text in files.items():
                z.writestr(name, text)
    except ClaudiosError:
        raise
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return dest


def default_zip_name(result: ScanResult) -> str:
    dom = re.sub(r"[^a-z0-9.-]", "-", result.snapshot.target.host.lower())[:60]
    return f"CLAUDIOS-report-{dom}-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
