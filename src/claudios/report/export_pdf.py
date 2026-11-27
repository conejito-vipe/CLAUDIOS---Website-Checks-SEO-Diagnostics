"""PDF-Export ohne zusätzliche Bibliothek: Qt zeichnet ein HTML-Dokument in eine PDF-Datei (QPdfWriter). Alles wird
maskiert; Zahlen werden nach Sprache formatiert (DE 1.000, EN 1,000). Qt wird erst beim Export geladen."""
from __future__ import annotations

import html
from pathlib import Path

from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.names import check_title
from ..core.numfmt import format_bytes, format_number
from ..core.redact import find_leaks
from .export_common import LABELS, SEVERITY, STATUS
from .report import build_report

ROW_COLORS = ("#FFFFFF", "#FFFFFF", "#FFF3CD", "#FDE2CF", "#F8D7DA")


def pdf_html(rep: dict, lang: str) -> str:
    labels, esc, sc = LABELS[lang], html.escape, rep["scan"]

    def num(value, digits: int = 0) -> str:
        return format_number(value, lang, digits)

    status = STATUS[lang].get(sc["status"], sc["status"])
    cats = ", ".join(f"{esc(key)}: {num(value)}" for key, value in rep["scores"]["categories"].items())
    parts = [
        f'<h1 style="color:#EE6A12">{esc(labels["report"])}</h1>',
        f"<p>{esc(sc['target'])} · {esc(labels['status'])}: {esc(status)} · {esc(labels['pages'])}: "
        f"{num(sc['pages_checked'])} · {esc(labels['data'])}: {esc(format_bytes(sc['bytes'], lang))}</p>",
    ]
    if sc["abort"]:
        info = sc["abort"][lang]
        parts.append(f"<p><b>{esc(info['title'])}</b> {esc(info['cause'])} {esc(info['action'])}</p>")
    parts.append(f"<p><b>{esc(labels['score'])}: {num(rep['scores']['overall'])}/100</b> ({cats})</p>")
    if rep["findings"]:
        head = "".join(f"<th>{esc(labels[key])}</th>" for key in ("sev", "check", "cnt", "msg", "ex"))
        rows = []
        for group in rep["findings"]:
            example = esc(group["example_urls"][0][:70]) if group["example_urls"] else ""
            rows.append(
                f'<tr><td bgcolor="{ROW_COLORS[group["severity"]]}">{esc(SEVERITY[lang][group["severity"]])}</td>'
                f'<td>{esc(check_title(group["check_id"], lang))}</td><td>{num(group["count"])}</td>'
                f'<td>{esc(group["msg_" + lang])}<br><small>{esc(group["evidence"])}</small></td>'
                f"<td><small>{example}</small></td></tr>")
        parts.append('<table border="1" cellspacing="0" cellpadding="4" width="100%">'
                     f'<tr bgcolor="#F3F6F8">{head}</tr>{"".join(rows)}</table>')
    else:
        parts.append(f"<p>{esc(labels['none'])}</p>")
    skipped = [c for c in rep["checks"] if c["status"] != "ran"]
    if skipped:
        items = "".join(f"<li>{esc(c['id'])}: {esc(c['title_' + lang])} ({esc(c['status'])})</li>" for c in skipped)
        parts.append(f"<h2>{esc(labels['notrun'])}</h2><ul>{items}</ul>")
    parts.append(f"<p><small>{esc(labels['disc'])}</small></p>")
    return "".join(parts)


def build_pdf(result, dest: Path | str, lang: str = "de") -> Path:
    dest = Path(dest)
    rep = build_report(result, lang)
    markup = pdf_html(rep, lang)
    leaks = find_leaks(markup)
    if leaks:
        raise ClaudiosError(E.EXPORT_FAILED, reason=f"possible secret in the export: {leaks[0]}")
    try:
        from PySide6.QtCore import QMarginsF
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    except ImportError:
        raise ClaudiosError(E.EXPORT_FAILED, reason="PySide6 is not installed") from None
    writer = QPdfWriter(str(dest))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    writer.setTitle(LABELS[lang]["report"])
    document = QTextDocument()
    document.setHtml(markup)
    document.print_(writer)
    del document, writer  # schließt die Datei
    if not dest.is_file() or dest.stat().st_size == 0:
        raise ClaudiosError(E.FS_ERROR, reason="pdf not written")
    return dest
