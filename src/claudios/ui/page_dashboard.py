"""Dashboard: Entwicklung der bisherigen Prüfungen, getrennt nach gescannter Domain (Wertung im Zeitverlauf, Veränderung je
Kategorie, Befunde je Scan) und der Ort, an dem die Bildschirmfotos liegen. Grundlage ist der Verlauf (nur Zusammenfassungen,
report/history.py). Zählt zu den Pro-Bereichen (core/angebot.py), ist aber ohne Freischaltung nicht gesperrt."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.probe_shots import shots_root
from ..i18n.strings import n, t
from ..report.history_tree import grouped, local_parts
from .scorecards import score_color
from .theme import LINE, MUTED

NAV_KEY = "nav.dashboard"
MAX_POINTS = 60


def series(records: list[dict]) -> list[dict]:
    """Die Scans einer Domain, älteste zuerst, mit Veränderung zum vorigen Scan (reine Funktion)."""
    ordered = sorted(records, key=lambda r: str(r["saved"]))[-MAX_POINTS:]
    out, previous = [], None
    for record in ordered:
        day, clock = local_parts(str(record["saved"]))
        out.append({"when": f"{day} {clock}", "score": int(record["score"]),
                    "delta": None if previous is None else int(record["score"]) - previous,
                    "findings": sum(int(f["count"]) for f in record["findings"] if f["severity"] >= 2),
                    "categories": dict(record.get("categories") or {})})
        previous = int(record["score"])
    return out


def category_trends(points: list[dict]) -> list[tuple[str, int, int]]:
    """(Kategorie, erster Wert, letzter Wert) über alle Scans; nur Kategorien, die in beiden vorkommen."""
    if len(points) < 2:
        return []
    first, last = points[0]["categories"], points[-1]["categories"]
    return [(name, int(first[name]), int(last[name])) for name in sorted(last) if name in first]


class TrendChart(QWidget):
    """Linie der Gesamtwertung (0 bis 100) über die Scans."""

    def __init__(self) -> None:
        super().__init__()
        self.values: list[int] = []
        self.setMinimumHeight(150)

    def set_values(self, values: list[int]) -> None:
        self.values = list(values)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt-Name)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(8, 8, self.width() - 16, self.height() - 24)
        painter.setPen(QPen(QColor(LINE), 1))
        for level in (0, 50, 100):
            y = area.bottom() - area.height() * level / 100
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QPen(QColor(MUTED), 1))
            painter.drawText(QPointF(area.left() + 2, y - 2), str(level))
            painter.setPen(QPen(QColor(LINE), 1))
        if not self.values:
            return
        step = area.width() / max(1, len(self.values) - 1)
        points = [QPointF(area.left() + (i * step if len(self.values) > 1 else area.width() / 2),
                          area.bottom() - area.height() * v / 100) for i, v in enumerate(self.values)]
        painter.setPen(QPen(QColor("#FF8A3D"), 2.5))
        for a, b in zip(points, points[1:], strict=False):
            painter.drawLine(a, b)
        for point, value in zip(points, self.values, strict=True):
            painter.setBrush(QColor(score_color(value)))
            painter.drawEllipse(point, 4.5, 4.5)


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._groups: dict[str, list[dict]] = {}
        self.title = QLabel()
        self.intro = QLabel()
        self.intro.setObjectName("muted")
        self.intro.setWordWrap(True)
        self.domain = QComboBox()
        self.chart = TrendChart()
        self.trend = QLabel()
        self.trend.setWordWrap(True)
        self.trend.setTextFormat(Qt.TextFormat.PlainText)
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.shots = QLabel()
        self.shots.setObjectName("muted")
        self.shots.setWordWrap(True)
        self.shots.setTextFormat(Qt.TextFormat.PlainText)
        self.shots.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.open_btn = QPushButton()
        self.empty = QLabel()
        self.empty.setObjectName("muted")
        self.empty.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        for widget in (self.title, self.intro, self.domain, self.empty, self.chart, self.trend):
            lay.addWidget(widget)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.shots)
        lay.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.domain.currentTextChanged.connect(self._show_domain)
        self.open_btn.clicked.connect(self._open_folder)

    def retranslate(self) -> None:
        self.title.setText(t("dash.title"))
        self.intro.setText(t("dash.intro"))
        self.open_btn.setText(t("dash.open"))
        self.table.setHorizontalHeaderLabels([t("dash.col.when"), t("dash.col.score"), t("dash.col.change"),
                                              t("dash.col.findings")])
        self.refresh()

    def refresh(self) -> None:
        try:
            groups = grouped()
        except Exception:  # noqa: BLE001 – der Verlauf ist nur eine Zugabe
            groups = []
        self._groups = {host: [rec for _day, scans in days for _clock, rec in scans] for host, days in groups}
        current = self.domain.currentText()
        self.domain.blockSignals(True)
        self.domain.clear()
        self.domain.addItems(sorted(self._groups))
        if current in self._groups:
            self.domain.setCurrentText(current)
        self.domain.blockSignals(False)
        has = bool(self._groups)
        self.empty.setText("" if has else t("dash.empty"))
        for widget in (self.domain, self.chart, self.trend, self.table):
            widget.setVisible(has)
        self.shots.setText(t("dash.shots", path=str(shots_root())))
        self._show_domain(self.domain.currentText())

    def _show_domain(self, host: str) -> None:
        points = series(self._groups.get(host, []))
        self.chart.set_values([p["score"] for p in points])
        self.table.setRowCount(0)
        for point in reversed(points):  # neueste zuerst
            row = self.table.rowCount()
            self.table.insertRow(row)
            delta = "–" if point["delta"] is None else ("+" if point["delta"] > 0 else "") + n(point["delta"])
            for col, value in enumerate((point["when"], f"{n(point['score'])}/100", delta, n(point["findings"]))):
                self.table.setItem(row, col, QTableWidgetItem(value))
        trends = category_trends(points)
        self.trend.setText("\n".join(
            t("dash.cat", name=name, first=n(a), last=n(b), delta=("+" if b - a > 0 else "") + n(b - a))
            for name, a, b in trends) if trends else t("dash.need_two"))

    def _open_folder(self) -> None:
        folder = shots_root()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().showEvent(event)
        self.refresh()


def create(window) -> DashboardPage:
    page = DashboardPage()
    signal = getattr(getattr(window, "scan", None), "scan_finished", None)
    if signal is not None:
        signal.connect(lambda _result: page.refresh())
    return page
