"""Seite 'Befunde': Filter und Detailansicht. Wird vom Hauptfenster automatisch gefunden und füllt sich bei jedem
fertigen Scan (window.scan.scan_finished). Die reine Logik (collect, not_run, visible, detail_text) kommt ohne Oberfläche aus."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..checks import load_all
from ..core.registry import REGISTRY
from ..i18n.strings import get_lang, n, t

NAV_KEY = "nav.findings"
MAX_URLS = 200


def _row(check_id: str, severity: int, de: str, en: str, evidence: str, urls: list[str], count: int,
         state: str | None, more: int = 0) -> dict:
    return {"check_id": check_id, "severity": severity, "msg_de": de, "msg_en": en, "evidence": evidence,
            "urls": urls, "count": count, "state": state, "more": more}


def collect(result) -> list[dict]:
    """Befunde gruppieren (Prüfung, Schwere, Text), sortiert nach Schwere. Adressen bis MAX_URLS je Gruppe."""
    groups: dict[tuple, dict] = {}
    for f in result.findings:
        key = (f.check_id, int(f.severity), f.msg_de, f.msg_en)
        group = groups.setdefault(key, {"evidence": f.evidence, "urls": {}, "count": 0})
        group["count"] += 1
        group["urls"].setdefault(f.url, None)
    rows = []
    for (cid, severity, de, en), group in groups.items():
        urls = list(group["urls"])
        rows.append(_row(cid, severity, de, en, group["evidence"], urls[:MAX_URLS], group["count"], None,
                         max(0, len(urls) - MAX_URLS)))
    return sorted(rows, key=lambda r: (-r["severity"], r["check_id"], r["msg_de"]))


def not_run(result) -> list[dict]:
    """Alle Prüfungen, die nicht 'ran' sind, mit dem Grund aus dem Status."""
    load_all()
    rows = []
    for cid, state in sorted(result.executed.items()):
        if state == "ran":
            continue
        meta = REGISTRY[cid].meta if cid in REGISTRY else None
        de = meta.title["de"] if meta else ""
        en = meta.title["en"] if meta else ""
        rows.append(_row(cid, -1, f"{de}: {state}", f"{en}: {state}", "", [], 0, state))
    return rows


def visible(rows: list[dict], minimum: int, category: str, query: str, lang: str) -> list[dict]:
    needle = query.strip().lower()
    out = []
    for row in rows:
        if row["state"] is None and row["severity"] < minimum:
            continue
        if category and not row["check_id"].startswith(category):
            continue
        if needle:
            haystack = " ".join([row["check_id"], row["msg_" + lang], row["evidence"], row["state"] or "",
                                 *row["urls"]]).lower()
            if needle not in haystack:
                continue
        out.append(row)
    return out


def detail_text(row: dict, lang: str) -> str:
    load_all()
    registered = REGISTRY.get(row["check_id"])
    meta = registered.meta if registered else None

    def pick(block: dict) -> str:
        return block.get(lang) or block.get("en", "")

    lines = [f"[{row['check_id']}] {pick(meta.title) if meta else ''}".rstrip()]
    if row["state"] is not None:
        lines += [f"{t('fnd.status')}: {row['state']}"]
    else:
        severity = t(f"sev.{row['severity']}")
        lines += [f"{t('fnd.severity')}: {severity} · {t('fnd.occurrences')}: {n(row['count'])}", "",
                  f"{t('fnd.finding')}: {row['msg_' + lang]}"]
        if row["evidence"]:
            lines.append(f"{t('fnd.evidence')}: {row['evidence']}")
        if row["urls"]:
            lines += ["", f"{t('fnd.pages')}:"] + [f"- {url}" for url in row["urls"]]
            if row["more"]:
                lines.append(t("fnd.more", count=n(row["more"])))
    if meta:
        lines += ["", f"{t('doc.why')} {pick(meta.why)}"]
        if row["state"] is not None:
            lines += ["", f"{t('doc.method')}: {pick(meta.method)}"]
        else:
            lines += ["", f"{t('doc.fix')}: {pick(meta.fix)}"]
        if meta.refs:
            lines += ["", f"{t('doc.refs')}:"] + [f"- {ref}" for ref in meta.refs]
    return "\n".join(lines)


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class FindingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self._findings: list[dict] = []
        self._notrun: list[dict] = []
        self._shown: list[dict] = []
        self.sev = QComboBox()
        self.cat = QComboBox()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.notrun = QCheckBox()
        self.count = _plain(QLabel())
        self.count.setObjectName("muted")
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        bar = QHBoxLayout()
        bar.addWidget(self.sev)
        bar.addWidget(self.cat)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.notrun)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setSizes([320, 220])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(bar)
        lay.addWidget(self.count)
        lay.addWidget(split, 1)
        self._fill_filters()
        self.sev.currentIndexChanged.connect(self.apply)
        self.cat.currentIndexChanged.connect(self.apply)
        self.search.textChanged.connect(self.apply)
        self.notrun.toggled.connect(self._mode_changed)
        self.table.itemSelectionChanged.connect(self.show_detail)

    def _rows(self) -> list[dict]:
        return self._notrun if self.notrun.isChecked() else self._findings

    def _fill_filters(self) -> None:
        sev_index, cat_data = self.sev.currentIndex(), self.cat.currentData()
        self.sev.blockSignals(True)
        self.cat.blockSignals(True)
        self.sev.clear()
        self.sev.addItem(t("fnd.all"), 0)
        for level in range(1, 5):
            self.sev.addItem(t("fnd.min", sev=t(f"sev.{level}")), level)
        self.sev.setCurrentIndex(max(sev_index, 0))
        self.cat.clear()
        self.cat.addItem(t("fnd.cat_all"), "")
        for cat in sorted({row["check_id"][:3] for row in self._rows()}):
            self.cat.addItem(cat, cat)
        index = self.cat.findData(cat_data) if cat_data else -1
        self.cat.setCurrentIndex(max(index, 0))
        self.sev.blockSignals(False)
        self.cat.blockSignals(False)

    def retranslate(self) -> None:
        self.table.setHorizontalHeaderLabels(
            [t("res.col.sev"), t("res.col.check"), t("res.col.count"), t("res.col.finding")])
        self.search.setPlaceholderText(t("fnd.search"))
        self.notrun.setText(t("fnd.notrun"))
        self._fill_filters()
        self.apply()

    def show_result(self, result) -> None:
        self.result = result
        self._findings = collect(result)
        self._notrun = not_run(result)
        self._fill_filters()
        self.apply()

    def _mode_changed(self, _checked: bool) -> None:
        self._fill_filters()
        self.apply()

    def apply(self, *_args) -> None:
        lang = get_lang()
        rows = visible(self._rows(), int(self.sev.currentData() or 0), str(self.cat.currentData() or ""),
                       self.search.text(), lang)
        self._shown = rows
        self.table.setRowCount(0)
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            if row["state"] is None:
                cells = (t(f"sev.{row['severity']}"), row["check_id"], n(row["count"]), row["msg_" + lang])
            else:
                cells = (t("fnd.state"), row["check_id"], "–", row["msg_" + lang])
            for col, value in enumerate(cells):
                self.table.setItem(index, col, QTableWidgetItem(value))
        self.count.setText(t("fnd.count", shown=n(len(rows)), total=n(len(self._rows()))) if self.result else "")
        if rows:
            self.table.selectRow(0)
        else:
            self.detail.setPlainText(t("fnd.none") if self.result else t("res.empty"))

    def show_detail(self) -> None:
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected or selected[0].row() >= len(self._shown):
            return
        self.detail.setPlainText(detail_text(self._shown[selected[0].row()], get_lang()))


def create(window) -> FindingsPage:
    page = FindingsPage()
    signal = getattr(getattr(window, "scan", None), "scan_finished", None)
    if signal is not None:
        signal.connect(page.show_result)
    return page
