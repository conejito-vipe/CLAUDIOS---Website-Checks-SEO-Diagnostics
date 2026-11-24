"""Verlaufsansicht: Website, darunter Tag, darunter jeder Scan. Ein Klick auf einen Scan zeigt seine Befunde."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ..core.numtext import localize_numbers
from ..i18n.strings import get_lang, n, t
from ..report.history_tree import grouped


def _status(value) -> str:
    try:
        return t(f"status.{value}")
    except KeyError:
        return str(value)


def detail_text(host: str, day: str, clock: str, record: dict, lang: str) -> str:
    lines = [t("hv.head", host=host, day=day, time=clock, status=_status(record.get("status")),
               score=n(record["score"])), ""]
    findings = sorted(record["findings"], key=lambda f: (-f["severity"], f["check_id"]))
    if not findings:
        lines.append(t("hv.none"))
    for item in findings:
        times = f" ({n(item['count'])}x)" if item["count"] > 1 else ""
        message = localize_numbers(item["msg_" + lang], lang)
        severity = item["severity"]
        lines.append(f"[{t(f'sev.{severity}')}] {item['check_id']}: {message}{times}")
    return "\n".join(lines)


class HistoryView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._records: dict[int, tuple[str, str, str, dict]] = {}
        self.title = QLabel()
        self.title.setObjectName("h2")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setMinimumHeight(180)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(140)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(self.title)
        lay.addWidget(self.tree, 2)
        lay.addWidget(self.detail, 1)
        self.tree.currentItemChanged.connect(self._show)

    def retranslate(self) -> None:
        self.title.setText(t("hv.title"))
        self.tree.setHeaderLabels([t("hv.col.when"), t("hv.col.score"), t("hv.col.status")])
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        self._records = {}
        try:
            groups = grouped()
        except Exception:  # noqa: BLE001 – der Verlauf ist nur eine Zugabe
            groups = []
        if not groups:
            self.detail.setPlainText(t("hv.empty"))
            return
        for host, days in groups:
            total = sum(len(scans) for _day, scans in days)
            top = QTreeWidgetItem([host, t("hv.scans", count=n(total)), ""])
            for day, scans in days:
                day_item = QTreeWidgetItem(top, [day, t("hv.scans", count=n(len(scans))), ""])
                for clock, record in scans:
                    item = QTreeWidgetItem(day_item, [clock, f"{n(record['score'])}/100", _status(record.get("status"))])
                    self._records[id(item)] = (host, day, clock, record)
            self.tree.addTopLevelItem(top)
        self.tree.expandToDepth(1)
        self.tree.resizeColumnToContents(0)
        self.detail.setPlainText(t("hv.pick"))

    def _show(self, current, _previous=None) -> None:
        entry = self._records.get(id(current)) if current is not None else None
        if entry is not None:
            host, day, clock, record = entry
            self.detail.setPlainText(detail_text(host, day, clock, record, get_lang()))
