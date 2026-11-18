"""Excel-Export (openpyxl, wird erst beim Export geladen). Vier Blätter: Übersicht, Befunde, Prüfungen, Seiten.
Zahlen sind echte Zahlen, Text mit Formelanfang wird entschärft, Steuerzeichen werden entfernt."""
from __future__ import annotations

import re
from pathlib import Path

from ..core.errors import ClaudiosError, ErrorCode as E
from .export_common import (
    LABELS,
    check_table,
    ensure_clean,
    finding_table,
    page_table,
    safe_cell,
    summary_table,
)
from .report import build_report

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _cell(value):
    if isinstance(value, str):
        value = _CONTROL.sub("", value)[:32000]
    return safe_cell(value)


def _sheet(workbook, first: bool, title: str, table: tuple[list, list[list]], widths: list[int], font) -> None:
    header, rows = table
    sheet = workbook.active if first else workbook.create_sheet()
    sheet.title = title
    sheet.append([_cell(item) for item in header])
    for cell in sheet[1]:
        cell.font = font
    for row in rows:
        sheet.append([_cell(item) for item in row])
    sheet.freeze_panes = "A2"
    for index, width in enumerate(widths):
        sheet.column_dimensions[chr(65 + index)].width = width
    if rows:
        sheet.auto_filter.ref = sheet.dimensions


def build_xlsx(result, dest: Path | str, lang: str = "de") -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise ClaudiosError(E.EXPORT_FAILED, reason="openpyxl is not installed") from None
    dest = Path(dest)
    rep = build_report(result, lang)
    labels = LABELS[lang]
    tables = [summary_table(rep, lang), finding_table(rep, lang), check_table(rep, lang), page_table(rep, lang)]
    ensure_clean(*tables)
    workbook, bold = Workbook(), Font(bold=True)
    _sheet(workbook, True, labels["s_summary"], tables[0], [28, 70], bold)
    _sheet(workbook, False, labels["s_findings"], tables[1], [12, 14, 9, 80, 40, 60], bold)
    _sheet(workbook, False, labels["s_checks"], tables[2], [14, 60, 40], bold)
    _sheet(workbook, False, labels["s_pages"], tables[3], [70, 9, 9, 16, 16, 30], bold)
    try:
        workbook.save(dest)
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return dest
