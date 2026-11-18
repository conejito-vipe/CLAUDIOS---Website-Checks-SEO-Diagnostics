"""CSV-Export der Befunde. UTF-8 mit BOM (Excel erkennt so die Umlaute), Trennzeichen ; (DE) oder , (EN),
Zellen mit Formelanfang werden entschärft (siehe export_common.safe_cell)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from ..core.errors import ClaudiosError, ErrorCode as E
from .export_common import ensure_clean, finding_table, safe_cell
from .report import build_report


def csv_text(rep: dict, lang: str) -> str:
    header, rows = finding_table(rep, lang)
    ensure_clean((header, rows))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";" if lang == "de" else ",", lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return buffer.getvalue()


def build_csv(result, dest: Path | str, lang: str = "de") -> Path:
    dest = Path(dest)
    text = csv_text(build_report(result, lang), lang)
    try:
        dest.write_text(text, encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    return dest
