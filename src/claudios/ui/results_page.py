"""Ergebnisseite: Sie zeigt nur Ergebnisse. Während eines Scans bleibt sie leer (kein Hinweis „noch kein Ergebnis“, keine
Fortschrittsanzeige, die steht in der Seitenleiste und auf der Scan-Seite). Kein Gesamtwert bei Abbruch (er wäre
irreführend) und nach einem Neustart der zuletzt gespeicherte Scan aus dem Verlauf (nur Zusammenfassung). Zahlen in den
Befundtexten bekommen den Tausendertrenner der Sprache."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QTableWidgetItem, QVBoxLayout, QWidget

from ..core.numfmt import format_bytes
from ..core.numtext import localize_numbers
from ..core.redact import redact_url
from ..i18n.strings import get_lang, n, t
from ..report.history_latest import latest_overall
from .pages import ResultsPage as _ResultsPage


class ResultsPage(_ResultsPage):
    _live_active = False

    def __init__(self) -> None:
        super().__init__()
        self.live_box = QWidget()
        box = QVBoxLayout(self.live_box)
        box.setContentsMargins(0, 0, 0, 6)
        box.setSpacing(4)
        self.live_text = QLabel()
        self.live_text.setWordWrap(True)
        self.live_text.setTextFormat(Qt.TextFormat.PlainText)
        self.live_bar = QProgressBar()
        self.live_bar.setRange(0, 100)
        self.live_bar.setTextVisible(False)
        box.addWidget(self.live_text)
        box.addWidget(self.live_bar)
        self.live_bar.setVisible(False)  # ein Balken für den ganzen Lauf: der in der Seitenleiste
        self.live_box.setVisible(False)
        self.layout().insertWidget(0, self.live_box)

    def mark_running(self) -> None:
        """Ein Scan läuft: kein Hinweis „noch kein Ergebnis“, erst nach dem Ende wieder."""
        self._live_active = True
        if self.result is None:
            self.summary.setText("")

    def show_live(self, message: str, percent: int) -> None:
        self.live_text.setText(t("res.live", message=message))
        self.live_bar.setValue(percent)
        self._live_active = True
        if self.result is None:
            self.summary.setText("")
        self.live_box.setVisible(True)

    def hide_live(self) -> None:
        self._live_active = False
        self.live_box.setVisible(False)
        if self.result is None:
            self.refresh()  # jetzt, nach dem Ende, darf der Hinweis „noch keine Ergebnisse“ erscheinen

    def _show_history(self) -> None:
        try:
            record = latest_overall()
        except Exception:  # noqa: BLE001 – der Verlauf ist nur eine Zugabe
            return
        if record is None:
            return
        lang = get_lang()
        self.summary.setText(t("res.history_note", host=record.get("host", ""), date=str(record["saved"])[:10],
                               score=n(record["score"])))
        for item in sorted(record["findings"], key=lambda f: (-f["severity"], f["check_id"])):
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = (t(f"sev.{item['severity']}"), item["check_id"], n(item["count"]),
                     localize_numbers(item["msg_" + lang], lang))
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _localize_table(self) -> None:
        lang = get_lang()
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 3)
            if cell is not None:
                cell.setText(localize_numbers(cell.text(), lang))

    def refresh(self) -> None:
        super().refresh()
        result = self.result
        if result is None:
            if self._live_active:
                self.summary.setText("")
                return
            self._show_history()
            return
        self._localize_table()
        if result.snapshot.status != "aborted":
            return
        snap = result.snapshot
        self.summary.setText(t(
            "res.summary_aborted", target=redact_url(snap.target.url), status=t("status.aborted"),
            pages=n(len(snap.pages)), requests=n(result.requests),
            size=format_bytes(result.bytes_total, get_lang())))
