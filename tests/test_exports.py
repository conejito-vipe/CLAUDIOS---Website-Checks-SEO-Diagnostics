import csv
import dataclasses
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from claudios.core.engine import ScanResult, run_checks
from claudios.core.findings import Finding, Severity as S
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.scoring import compute_scores
from claudios.core.snapshot import Page, Snapshot
from claudios.i18n.strings import TEXTS, get_lang, set_lang
from claudios.report import export_pdf, history
from claudios.report.export_common import safe_cell
from claudios.report.export_csv import build_csv, csv_text
from claudios.report.export_xlsx import build_xlsx
from claudios.report.focus_zip import build_focus_zip
from claudios.report.prompts import FOCI, PREFIXES, prompt_for
from claudios.report.report import PROMPT, build_report

BAD = '<html><head></head><body><img src="a.png"><a href="https://x.example" target="_blank">x</a></body></html>'
GOOD = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>A good page title</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="description" content="This is a sample description that is long enough to pass the length check.">'
        '<link rel="canonical" href="https://example.com/"></head><body><main><h1>Hello</h1></main></body></html>')
EVIL = Finding("HTM-IMG-001", S.WARNING, "https://example.com/", "=SUM(1+1)", "=SUM(1+1)")


def make_result(html, extra=()):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html=html,
                           content_type="text/html; charset=utf-8"))
    snap.status = "complete"
    findings, executed = run_checks(snap, 1, "standard")
    findings = findings + list(extra)
    return ScanResult(snap, findings, executed, compute_scores(findings, executed), requests=1, bytes_total=len(html))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


@pytest.mark.parametrize("value,expected", [
    ("=1+1", "'=1+1"), ("+a", "'+a"), ("-a", "'-a"), ("@a", "'@a"), ("\tx", "'\tx"), ("\rx", "'\rx"),
    ("normal", "normal"), ("a=b", "a=b"), (5, 5), (-5, -5), (None, None)])
def test_formula_prefixes_are_defused_and_numbers_stay_numbers(value, expected):
    assert safe_cell(value) == expected


def test_csv_has_a_delimiter_per_language_and_defuses_formulas(tmp_path):
    result = make_result(BAD, [EVIL])
    rows = list(csv.reader(io.StringIO(csv_text(build_report(result, "de"), "de")), delimiter=";"))
    assert len(rows[0]) == 6 and rows[0][0] == "Schwere"
    hit = next(r for r in rows if r[1] == "HTM-IMG-001" and "SUM" in r[3])
    assert hit[3] == "'=SUM(1+1)" and hit[2] == "1"
    english = csv_text(build_report(result, "en"), "en")
    assert english.splitlines()[0].count(",") == 5
    out = build_csv(result, tmp_path / "f.csv", "de")
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_excel_has_four_sheets_real_numbers_and_defused_text(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    out = build_xlsx(make_result(BAD, [EVIL]), tmp_path / "f.xlsx", "de")
    book = openpyxl.load_workbook(out)
    assert book.sheetnames == ["Übersicht", "Befunde", "Prüfungen", "Seiten"]
    sheet = book["Befunde"]
    rows = list(sheet.iter_rows(min_row=2))
    hit = next(r for r in rows if r[3].value and "SUM" in r[3].value)
    assert hit[3].value == "'=SUM(1+1)" and hit[3].data_type == "s"
    assert isinstance(hit[2].value, int)
    assert book["Seiten"]["A2"].value == "https://example.com/"


def test_pdf_markup_escapes_everything():
    evil = Finding("HTM-IMG-001", S.WARNING, "https://example.com/", "<b>x</b>", "<b>x</b>")
    markup = export_pdf.pdf_html(build_report(make_result(BAD, [evil]), "en"), "en")
    assert "&lt;b&gt;x&lt;/b&gt;" in markup and "<b>x</b>" not in markup


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_pdf_file_is_written(qapp, tmp_path):
    out = export_pdf.build_pdf(make_result(BAD), tmp_path / "f.pdf", "de")
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000


def test_prompts_exist_for_every_focus_and_language():
    for lang in ("de", "en"):
        assert prompt_for("general", lang) == PROMPT[lang]
        for focus in FOCI[1:]:
            text = prompt_for(focus, lang)
            assert PREFIXES[focus][0] in text and len(text) > 400
    with pytest.raises(ValueError):
        prompt_for("nope", "de")


def test_focus_zip_filters_the_summary_but_keeps_the_full_report(tmp_path):
    result = make_result(BAD)
    out = build_focus_zip(result, tmp_path / "f.zip", "en", "seo")
    with zipfile.ZipFile(out) as archive:
        texts = {name: archive.read(name).decode("utf-8") for name in archive.namelist()}
    assert set(texts) == {"prompt.md", "summary.md", "report.json", "report.html", "manifest.json"}
    assert "focus on SEO" in texts["prompt.md"]
    assert "SEO-MET-001" in texts["summary.md"] and "SEC-" not in texts["summary.md"]
    assert any(g["check_id"].startswith("SEC-") for g in json.loads(texts["report.json"])["findings"])
    manifest = json.loads(texts["manifest.json"])
    assert manifest["focus"] == "seo"
    for name, info in manifest["files"].items():
        assert hashlib.sha256(texts[name].encode()).hexdigest() == info["sha256"]


def test_history_is_on_by_default_and_stores_nothing_when_switched_off(env):
    assert history.enabled() is True
    history.set_enabled(False)
    assert history.enabled() is False
    assert history.save(history.record_of(make_result(BAD))) is None
    assert not history.history_dir().exists()


def test_history_saves_compares_prunes_and_deletes(env, monkeypatch):
    history.set_enabled(True)
    old = history.record_of(make_result(BAD), datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC))
    new = history.record_of(make_result(GOOD), datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC))
    assert "url" not in json.dumps(old) and "example.com/" not in json.dumps(old["findings"])
    history.save(old, datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert history.latest("example.com")["saved"].startswith("2025-01-01")
    diff = history.compare(history.latest("example.com"), new)
    assert any(f["check_id"] == "HTM-IMG-001" for f in diff["resolved"])
    assert diff["delta"] == new["score"] - old["score"] and diff["level_changed"] is False
    monkeypatch.setattr(history, "LIMITS", dataclasses.replace(LIMITS, history_max_per_domain=2))
    history.save(new, datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC))
    history.save(new, datetime(2025, 1, 3, 12, 0, 0, tzinfo=UTC))
    assert history.count("example.com") == 2 and history.latest("example.com")["saved"].startswith("2025-01-02")
    assert history.delete_all() == 2 and history.count() == 0


def test_damaged_or_foreign_history_files_are_ignored(env):
    history.set_enabled(True)
    folder = history.history_dir()
    folder.mkdir(parents=True)
    (folder / "example.com_20250101T000000000000.json").write_text("not json", "utf-8")
    (folder / "example.com_20250102T000000000000.json").write_text('{"version": 9}', "utf-8")
    (folder / "example.com_20250103T000000000000.json").write_text("[" * 100_000, "utf-8")
    assert history.latest("example.com") is None


def test_texts_exist_in_both_languages_and_format_cleanly():
    keys = [k for k in TEXTS["de"] if k.startswith("exp.")] + ["nav.export"]
    assert len(keys) >= 35
    values = {"count": "1", "date": "2025-01-01", "old": "1", "new": "2", "delta": "+1", "target": "x",
              "status": "s", "score": "9"}
    for key in keys:
        for lang in ("de", "en"):
            assert TEXTS[lang][key].strip()
            TEXTS[lang][key].format_map(values)
    assert set(TEXTS["de"]) == set(TEXTS["en"])


def test_the_export_page_fills_after_a_scan_and_compares(qapp, env):
    from PySide6.QtCore import QObject, Signal

    from claudios.ui import page_export

    class Scan(QObject):
        scan_finished = Signal(object)

    old = get_lang()
    try:
        set_lang("de")
        scan = Scan()
        page = page_export.create(SimpleNamespace(scan=scan))
        page.retranslate()
        assert not page.csv_btn.isEnabled() and page.cmp.toPlainText() == TEXTS["de"]["exp.none"]
        scan.scan_finished.emit(make_result(BAD))
        assert page.csv_btn.isEnabled() and "Kein früherer Scan" in page.cmp.toPlainText()
        page.hist_box.setChecked(True)
        scan.scan_finished.emit(make_result(BAD))  # speichert
        scan.scan_finished.emit(make_result(GOOD))  # vergleicht mit dem gespeicherten
        text = page.cmp.toPlainText()
        assert "Vergleich mit dem Scan vom" in text and "Behoben" in text
        assert history.count() >= 2
    finally:
        set_lang(old)
