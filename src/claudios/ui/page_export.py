"""Seite 'Export & Verlauf': CSV, Excel, PDF, ZIP mit Schwerpunkt, der Vergleich mit dem letzten gespeicherten Scan und der
Verlauf aller gescannten Websites nach Domain und Tag. Wird vom Hauptfenster automatisch gefunden und füllt sich bei jedem
fertigen Scan (window.scan.scan_finished)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.numfmt import format_bytes
from ..core.redact import redact_url
from ..i18n.strings import get_lang, n, t
from ..report import history
from ..report.export_csv import build_csv
from ..report.export_pdf import build_pdf
from ..report.export_xlsx import build_xlsx
from ..report.focus_zip import build_focus_zip, focus_zip_preview
from ..report.prompts import FOCI
from ..report.report import default_zip_name
from .dialogs import error_info, show_error
from .history_view import HistoryView

NAV_KEY = "nav.export"
MAX_LINES = 30
KINDS = {"csv": (build_csv, "CSV (*.csv)"), "xlsx": (build_xlsx, "Excel (*.xlsx)"), "pdf": (build_pdf, "PDF (*.pdf)")}


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _signed(value: int) -> str:
    return ("+" if value > 0 else "") + n(value)


def diff_text(diff: dict, lang: str) -> str:
    """Der Vergleich als Text (reine Funktion, nutzt die aktuelle Sprache für die Beschriftungen)."""
    lines = [t("exp.cmp.head", date=diff["old_date"][:10], old=n(diff["old_score"]), new=n(diff["new_score"]),
               delta=_signed(diff["delta"]))]
    if diff["level_changed"]:
        lines.append(t("exp.cmp.level_note"))

    def section(key: str, items: list[str]) -> None:
        if not items:
            return
        lines.extend(["", t(key, count=n(len(items)))])
        lines.extend(items[:MAX_LINES])
        if len(items) > MAX_LINES:
            lines.append(t("exp.cmp.more", count=n(len(items) - MAX_LINES)))

    def entry(finding: dict) -> str:
        return f"- [{t('sev.' + str(finding['severity']))}] {finding['check_id']}: {finding['msg_' + lang]}"

    section("exp.cmp.new", [entry(f) for f in diff["added"]])
    section("exp.cmp.resolved", [entry(f) for f in diff["resolved"]])
    section("exp.cmp.changed", [f"{entry(new)} ({n(old['count'])} → {n(new['count'])})"
                                for old, new in diff["changed"]])
    lines.extend(["", t("exp.cmp.same", count=n(diff["same"]))])
    return "\n".join(lines)


class ExportPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self._diff: dict | None = None
        self._aborted = False
        self.title = _plain(QLabel())
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.current = _plain(QLabel())
        self.csv_btn = QPushButton()
        self.xlsx_btn = QPushButton()
        self.pdf_btn = QPushButton()
        self.focus_lbl = _plain(QLabel())
        self.focus = QComboBox()
        for key in FOCI:
            self.focus.addItem("", key)
        self.zip_btn = QPushButton()
        self.hist_title = _plain(QLabel())
        self.hist_box = QCheckBox()
        self.hist_info = _plain(QLabel())
        self.hist_info.setObjectName("muted")
        self.hist_delete = QPushButton()
        self.cmp = QPlainTextEdit()
        self.cmp.setReadOnly(True)
        self.hist_view = HistoryView()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for widget in (self.title, self.intro, self.current, self.csv_btn, self.xlsx_btn, self.pdf_btn,
                       self.focus_lbl, self.focus, self.zip_btn, self.hist_title, self.hist_box, self.hist_info,
                       self.hist_delete):
            lay.addWidget(widget)
        lay.addWidget(self.cmp, 1)
        lay.addWidget(self.hist_view, 2)
        self.csv_btn.clicked.connect(lambda: self.export_file("csv"))
        self.xlsx_btn.clicked.connect(lambda: self.export_file("xlsx"))
        self.pdf_btn.clicked.connect(lambda: self.export_file("pdf"))
        self.zip_btn.clicked.connect(self.export_zip)
        self.hist_box.toggled.connect(self._toggle_history)
        self.hist_delete.clicked.connect(self.delete_history)

    def retranslate(self) -> None:
        self.title.setText(t("exp.title"))
        self.intro.setText(t("exp.intro"))
        self.csv_btn.setText(t("exp.csv"))
        self.xlsx_btn.setText(t("exp.xlsx"))
        self.pdf_btn.setText(t("exp.pdf"))
        self.focus_lbl.setText(t("exp.focus_lbl"))
        for index, key in enumerate(FOCI):
            self.focus.setItemText(index, t(f"exp.focus.{key}"))
        self.zip_btn.setText(t("exp.zip_focus"))
        self.hist_title.setText(t("exp.hist.title"))
        self.hist_box.setText(t("exp.hist.switch"))
        self.hist_delete.setText(t("exp.hist.delete"))
        self.hist_view.retranslate()
        self._refresh()

    def show_result(self, result) -> None:
        self.result, self._diff = result, None
        self._aborted = result.snapshot.status == "aborted"
        if not self._aborted:  # ein abgebrochener Scan taugt nicht für den Vergleich
            try:
                record = history.record_of(result)
                previous = history.latest(record["host"])
                history.save(record)
                if previous is not None:
                    self._diff = history.compare(previous, record)
            except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund gezeigt
                show_error(self, error_info(exc))
        self._refresh()

    def _refresh(self) -> None:
        result = self.result
        for button in (self.csv_btn, self.xlsx_btn, self.pdf_btn, self.zip_btn):
            button.setEnabled(result is not None)
        self.hist_box.blockSignals(True)
        self.hist_box.setChecked(history.enabled())
        self.hist_box.blockSignals(False)
        stored = history.count()
        self.hist_info.setText(f"{t('exp.hist.info')}\n{t('exp.hist.stored', count=n(stored))}")
        self.hist_delete.setEnabled(stored > 0)
        self.hist_view.refresh()
        if result is None:
            self.current.setText("")
            self.cmp.setPlainText(t("exp.none"))
            return
        snap = result.snapshot
        self.current.setText(t("exp.current", target=redact_url(snap.target.url),
                               status=t(f"status.{snap.status}"), score=n(result.scores["overall"])))
        if self._aborted:
            self.cmp.setPlainText(t("exp.cmp.aborted"))
        elif self._diff is None:
            self.cmp.setPlainText(t("exp.cmp.none"))
        else:
            self.cmp.setPlainText(diff_text(self._diff, get_lang()))

    def export_file(self, kind: str) -> None:
        if self.result is None:
            return
        builder, file_filter = KINDS[kind]
        default = str(Path.home() / f"{default_zip_name(self.result)[:-4]}.{kind}")
        path, _filter = QFileDialog.getSaveFileName(self, t(f"exp.dialog_{kind}"), default, file_filter)
        if not path:
            return
        try:
            builder(self.result, path, get_lang())
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund gezeigt
            show_error(self, error_info(exc))
            return
        QMessageBox.information(self, t("export.title"), t("export.saved", path=path))

    def export_zip(self) -> None:
        if self.result is None:
            return
        lang, focus = get_lang(), str(self.focus.currentData())
        try:
            preview = focus_zip_preview(self.result, lang, focus)
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
            return
        files = "\n".join(f"- {name} ({format_bytes(size, lang)})" for name, size in preview)
        if QMessageBox.question(self, t("export.title"), t("export.text", files=files)) != QMessageBox.StandardButton.Yes:
            return
        default = str(Path.home() / default_zip_name(self.result))
        path, _filter = QFileDialog.getSaveFileName(self, t("export.dialog"), default, "ZIP (*.zip)")
        if not path:
            return
        try:
            build_focus_zip(self.result, path, lang, focus)
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
            return
        QMessageBox.information(self, t("export.title"), t("export.saved", path=path))

    def _toggle_history(self, checked: bool) -> None:
        try:
            history.set_enabled(checked)
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
        self._refresh()

    def delete_history(self) -> None:
        if QMessageBox.question(self, t("exp.hist.title"), t("exp.hist.delete_ask")) != QMessageBox.StandardButton.Yes:
            return
        removed = history.delete_all()
        QMessageBox.information(self, t("exp.hist.title"), t("exp.hist.deleted", count=n(removed)))
        self._refresh()


def create(window) -> ExportPage:
    page = ExportPage()
    signal = getattr(getattr(window, "scan", None), "scan_finished", None)
    if signal is not None:
        signal.connect(page.show_result)
    return page
