"""Seiten des Hauptfensters: Scan, Ergebnisse, Dokumentation, Einstellungen."""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.audit_log import AuditLog
from ..core.errors import ClaudiosError, ErrorCode
from ..core.limits import LIMITS
from ..core.numfmt import format_bytes
from ..core.redact import redact_url
from ..docs import render_doc
from ..gsc import session
from ..i18n.strings import get_lang, n, t
from ..paths import data_dir
from ..report.report import build_zip, default_zip_name, group_findings, zip_preview
from ..settings import save as save_settings
from .checknames import check_title
from .cooldown import remaining as cooldown_remaining
from .dialogs import error_info, show_error
from .expert_box import ExpertBox
from .explainpanel import ExplainPanel
from .levelinfo import KEYS as LEVEL_KEYS, level_info
from .linktext import LinkText
from .scanprogress import PhaseClock, format_duration, overall_percent
from .scorecards import CategoryRow, ScoreRing, style_severity
from .urlinput import clean_input
from .worker import ScanThread

PROFILES = ("quick", "standard", "deep")
INFO_ITEMS = 4


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _confirm(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("app.title"), text) == QMessageBox.StandardButton.Yes


def _audit_path() -> Path:
    return data_dir() / "logs" / "audit.jsonl"


class ScanPage(QWidget):
    scan_finished = Signal(object)
    activity = Signal(str, int, str)   # Text, Prozent, Abschnitt (crawl, probe, link, check)
    running_changed = Signal(bool)

    def __init__(self, get_settings) -> None:
        super().__init__()
        self._get_settings = get_settings
        self._thread: ScanThread | None = None
        self.url_lbl = _plain(QLabel())
        self.url = QLineEdit()
        self.profile_lbl = _plain(QLabel())
        self.profile = QComboBox()
        for key in PROFILES:
            self.profile.addItem("", key)
        self.profile.setCurrentIndex(1)
        self.profile_info = _plain(QLabel())
        self.profile_info.setObjectName("muted")
        self.confirm = QCheckBox()
        self.level_lbl = _plain(QLabel())
        self.level_lbl.setObjectName("muted")
        self.expert = ExpertBox(self.open_services)
        self.google = QPushButton()
        self.start_btn = QPushButton()
        self.start_btn.setObjectName("primary")
        self.cancel_btn = QPushButton()
        self.cancel_btn.setEnabled(False)
        self.cool_lbl = _plain(QLabel())
        self.cool_bar = QProgressBar()
        self.cool_bar.setRange(0, LIMITS.cooldown_seconds)
        self.cool_bar.setFormat("%v s")
        self.cool_lbl.setVisible(False)
        self.cool_bar.setVisible(False)
        self._cool_timer = QTimer(self)
        self._cool_timer.setInterval(1000)
        self._cool_timer.timeout.connect(self._tick_cooldown)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.status = _plain(QLabel())
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        self.title = _plain(QLabel())
        self.subtitle = _plain(QLabel())
        self.subtitle.setObjectName("subtitle")
        self.info_title = _plain(QLabel())
        self.info_title.setObjectName("h2")
        self.info_heads = [_plain(QLabel()) for _ in range(INFO_ITEMS)]
        self.info_bodies = [_plain(QLabel()) for _ in range(INFO_ITEMS)]
        form = QFrame()
        form.setObjectName("panel")
        lay = QVBoxLayout(form)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)
        for widget in (self.url_lbl, self.url, self.profile_lbl, self.profile, self.profile_info, self.confirm,
                       self.level_lbl, self.expert, self.google, self.start_btn, self.cancel_btn, self.cool_lbl,
                       self.cool_bar, self.bar, self.status):
            lay.addWidget(widget)
        lay.addWidget(self.log, 1)
        info = QFrame()
        info.setObjectName("panel")
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(20, 18, 20, 18)
        info_lay.setSpacing(14)
        info_lay.addWidget(self.info_title)
        for head, body in zip(self.info_heads, self.info_bodies, strict=True):
            item = QFrame()
            item.setObjectName("infoitem")
            item_lay = QVBoxLayout(item)
            item_lay.setContentsMargins(12, 0, 0, 0)
            item_lay.setSpacing(2)
            head.setObjectName("infohead")
            body.setObjectName("muted")
            item_lay.addWidget(head)
            item_lay.addWidget(body)
            info_lay.addWidget(item)
        info_lay.addStretch(1)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(form, 3)
        columns.addWidget(info, 2, Qt.AlignmentFlag.AlignTop)
        inner = QWidget()
        page_lay = QVBoxLayout(inner)
        page_lay.setContentsMargins(4, 0, 12, 4)
        page_lay.setSpacing(6)
        page_lay.addWidget(self.title)
        page_lay.addWidget(self.subtitle)
        page_lay.addSpacing(10)
        page_lay.addLayout(columns, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        scroll.viewport().setAutoFillBackground(False)
        inner.setAutoFillBackground(False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.start_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)
        self.google.clicked.connect(self.open_google)
        self.url.returnPressed.connect(self.start)
        self.url.textChanged.connect(self._update_level)
        self.profile.currentIndexChanged.connect(self._update_profile_info)
        self.status_key = "scan.idle"

    def retranslate(self) -> None:
        self.title.setText(t("scan.title"))
        self.subtitle.setText(t("scan.subtitle"))
        self.info_title.setText(t("scan.info.title"))
        for index in range(INFO_ITEMS):
            self.info_heads[index].setText(t(f"scan.info.{index + 1}.h"))
            self.info_bodies[index].setText(t(f"scan.info.{index + 1}.b"))
        self.url_lbl.setText(t("scan.url"))
        self.url.setPlaceholderText(t("scan.url_ph"))
        self.profile_lbl.setText(t("scan.profile"))
        for index, key in enumerate(PROFILES):
            self.profile.setItemText(index, t(f"profile.{key}"))
        self._update_profile_info()
        self.confirm.setText(t("scan.confirm"))
        self._update_level()
        self.expert.retranslate()
        self.google.setText(t("scan.google"))
        self.start_btn.setText(t("scan.start"))
        self.cancel_btn.setText(t("scan.cancel"))
        if self._thread is None:
            self.status.setText(t(self.status_key))

    def _local(self) -> bool:
        return bool(self._get_settings().get("allow_localhost"))

    def _update_profile_info(self, *_args) -> None:
        key = str(self.profile.currentData() or "standard")
        self.profile_info.setText(t(
            f"scan.profile_info.{key}", quick=n(LIMITS.quick_pages), pages=n(LIMITS.pages_level1),
            pages2=n(LIMITS.pages_level2), depth=n(LIMITS.max_depth), sample=n(LIMITS.browser_sample_standard),
            deep=n(LIMITS.browser_sample_deep)))

    def _update_level(self, *_args) -> None:
        """Zeigt, welche Stufe für die eingegebene Domain gilt (nur Anzeige, geprüft wird vor dem Scan live)."""
        local = self._local()
        info = level_info(clean_input(self.url.text(), local), local, session.SESSION)
        pages = LIMITS.pages_level2 if info.level == 2 or info.state == "armed" else LIMITS.pages_level1
        self.level_lbl.setText(t(LEVEL_KEYS[info.state], pages=n(pages), depth=n(LIMITS.max_depth), prop=info.prop))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().showEvent(event)
        self._update_level()  # der Zustand kann sich auf der Seite Search Console geändert haben
        self._start_cooldown()

    def _show_cooldown(self, left: int) -> None:
        visible = left > 0
        self.cool_lbl.setVisible(visible)
        self.cool_bar.setVisible(visible)
        if visible:
            self.cool_bar.setValue(min(left, LIMITS.cooldown_seconds))
            self.cool_lbl.setText(t("scan.cooldown", seconds=n(left)))

    def _start_cooldown(self) -> None:
        left = cooldown_remaining(_audit_path())
        self._show_cooldown(left)
        if left > 0 and not self._cool_timer.isActive():
            self._cool_timer.start()

    def _tick_cooldown(self) -> None:
        left = cooldown_remaining(_audit_path())
        self._show_cooldown(left)
        if left <= 0:
            self._cool_timer.stop()

    def _goto(self, key: str) -> None:
        window = self.window()
        keys = getattr(window, "nav_keys", ())
        nav = getattr(window, "nav", None)
        if nav is not None and key in keys:
            nav.setCurrentRow(keys.index(key))

    def open_google(self) -> None:
        self._goto("nav.gsc")

    def open_services(self) -> None:
        self._goto("nav.services")

    def busy(self) -> bool:
        return self._thread is not None

    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        for widget in (self.url, self.profile, self.confirm, self.google, self.expert):
            widget.setEnabled(not running)
        self.running_changed.emit(running)

    def start(self) -> None:
        if self._thread is not None:
            return
        local = self._local()
        raw = clean_input(self.url.text(), local)
        if raw != self.url.text():
            self.url.setText(raw)
        names = self.expert.external_names()
        if names and not _confirm(self, t("scan.ext_ask", names=", ".join(names))):
            return
        try:
            audit = AuditLog(_audit_path())
        except OSError as exc:
            show_error(self, error_info(ClaudiosError(ErrorCode.FS_ERROR, reason=type(exc).__name__)))
            return
        kwargs = {
            "raw_url": raw,
            "level": 1,
            "profile": self.profile.currentData(),
            "confirmed": self.confirm.isChecked(),
            "audit": audit,
            "lock_path": data_dir() / "scan.lock",
            "allow_localhost": local,
        }
        self.log.clear()
        self._last_marker = None
        self._clock = PhaseClock()
        self._check_now = None
        self._t0 = time.monotonic()
        self._last_marker = None
        self.bar.setValue(0)
        self.status.setText(t("scan.running"))
        self._set_running(True)
        thread = ScanThread(kwargs)
        thread.progress.connect(self._on_progress)
        thread.done.connect(self._on_done)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._cleanup)
        self._thread = thread
        thread.start()

    def cancel(self) -> None:
        if self._thread is not None:
            self._thread.cancel()
            self.cancel_btn.setEnabled(False)
            self.status.setText(t("scan.cancelling"))

    def shutdown(self) -> None:
        self._cool_timer.stop()
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.cancel()
            thread.wait(20000)

    @staticmethod
    def _check_name(check_id: str) -> str:
        try:
            from ..core.registry import REGISTRY

            return REGISTRY[check_id].meta.title[get_lang()]
        except (KeyError, AttributeError):
            return check_id

    def _log_top(self, text: str) -> None:
        """Die neueste Aktivität steht oben, das Protokoll läuft nach unten."""
        cursor = QTextCursor(self.log.document())
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.insertText(text + "\n")

    def _time_checks(self, kind: str, detail: str) -> None:
        """Schreibt für jede Prüfung, die länger als 5 Sekunden brauchte, die Dauer ins Protokoll."""
        now = time.monotonic()
        previous = getattr(self, "_check_now", None)
        if previous is not None and (kind != "check" or previous[0] != detail):
            took = now - previous[1]
            if took >= 5:
                logging.getLogger("claudios").info("check %s took %.0f s", previous[0], took)
            self._check_now = None
        if kind == "check" and getattr(self, "_check_now", None) is None:
            self._check_now = (detail, now)

    def _on_progress(self, stage: str, cur: int, total: int) -> None:
        kind, _sep, detail = stage.partition(":")
        total = max(total, 1)
        self._time_checks(kind, detail)
        note = None
        if kind == "crawl":
            message, note = t("scan.crawl_count", cur=n(cur), total=n(total)), "scan.stage.crawl"
        elif kind == "link":
            message = t("scan.link_count", cur=n(cur), total=n(total), url=redact_url(detail)[:90])
            note = "scan.stage.links"
        elif kind == "probe":
            try:
                name = t("probe." + detail)
            except KeyError:
                name = detail
            message = t("scan.probe", cur=n(cur), total=n(total), name=name)
        elif kind == "check":
            message = t("scan.check_count", cur=n(cur), total=n(total), name=self._check_name(detail))
            note = "scan.stage.checks"
        else:
            message = t("scan.progress", cur=n(cur), total=n(total))
        percent = overall_percent(kind, cur, total)
        eta = self._clock.update(kind, cur, total)
        line = message
        if eta is not None:
            line += "\n\n" + t("scan.eta", time=format_duration(eta, get_lang()))
        self.bar.setValue(percent)
        self.status.setText(line)  # eine Zeile, die hochzählt; das Protokoll bekommt nur eine Zeile je Abschnitt
        marker = (kind, detail) if kind == "probe" else (kind, "")
        if marker != self._last_marker:
            self._last_marker = marker
            logging.getLogger("claudios").info("scan stage %s %s/%s%s", kind, cur, total,
                                               f" {detail}" if kind == "probe" else "")
            self._log_top(t(note) if note else message)
        self.activity.emit(line, percent, kind)

    def _on_done(self, result) -> None:
        self._time_checks("end", "")
        self.confirm.setChecked(False)  # Bestätigung gilt nur für einen Scan
        snap = result.snapshot
        self.bar.setValue(100)
        self.status_key = "scan.idle"
        message = t("scan.done_level", status=t(f"status.{snap.status}"), level=n(snap.level))
        self.status.setText(message)
        self._log_top(message)
        self.scan_finished.emit(result)
        if snap.abort:
            show_error(self, snap.abort[get_lang()])

    def _on_failed(self, exc: BaseException) -> None:
        self.confirm.setChecked(False)
        self.status.setText(t("scan.idle"))
        show_error(self, error_info(exc))

    def _cleanup(self) -> None:
        self._thread = None
        self._set_running(False)
        self._start_cooldown()


class ResultsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self.summary = _plain(QLabel())
        self.notrun = _plain(QLabel())
        self.notrun.setObjectName("muted")
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in (0, 2):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 230)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self.export)
        self.ring = ScoreRing()
        self.categories = CategoryRow()
        self.head = QWidget()
        head = QHBoxLayout(self.head)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(16)
        head.addWidget(self.ring)
        head.addWidget(self.categories, 1)
        self.head.setVisible(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.head)
        lay.addWidget(self.summary)
        lay.addWidget(self.notrun)
        self.explain = ExplainPanel()
        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self.table, 1)
        body.addWidget(self.explain)
        lay.addLayout(body, 1)
        lay.addWidget(self.export_btn)

    def show_result(self, result) -> None:
        self.result = result
        self.refresh()

    def retranslate(self) -> None:
        self.table.setHorizontalHeaderLabels(
            [t("res.col.sev"), t("res.col.check"), t("res.col.count"), t("res.col.finding")])
        self.export_btn.setText(t("res.export"))
        self.explain.retranslate()
        self.refresh()

    def refresh(self) -> None:
        result = self.result
        self.table.setRowCount(0)
        self.explain.show_for(None)
        self.export_btn.setEnabled(result is not None)
        if result is None:
            self.summary.setText(t("res.empty"))
            self.notrun.setText("")
            self.head.setVisible(False)
            return
        aborted = result.snapshot.status == "aborted"  # ohne Gesamtwert: er wäre irreführend
        self.ring.set_value(None if aborted else result.scores["overall"])
        self.categories.set_scores({} if aborted else result.scores["categories"])
        self.head.setVisible(not aborted)
        snap, lang = result.snapshot, get_lang()
        self.summary.setText(t(
            "res.summary", target=redact_url(snap.target.url), status=t(f"status.{snap.status}"),
            score=n(result.scores["overall"]), pages=n(len(snap.pages)), requests=n(result.requests),
            size=format_bytes(result.bytes_total, lang)))
        skipped = [state for state in result.executed.values() if state != "ran"]
        self.notrun.setText(t("res.notrun", count=n(len(skipped))) if skipped else "")
        for group in group_findings(result.findings):
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = (t(f"sev.{group['severity']}"), check_title(group["check_id"], lang), n(group["count"]),
                     group["msg_" + lang])
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if col == 1:
                    item.setData(Qt.ItemDataRole.UserRole, group["check_id"])
                item.setToolTip("\n".join([group["evidence"], *group["example_urls"]]))
                if col == 0:
                    style_severity(item, group["severity"])
                self.table.setItem(row, col, item)

    def export(self) -> None:
        if self.result is None:
            return
        lang = get_lang()
        try:
            preview = zip_preview(self.result, lang)
        except ClaudiosError as exc:
            show_error(self, error_info(exc))
            return
        files = "\n".join(f"- {name} ({format_bytes(size, lang)})" for name, size in preview)
        answer = QMessageBox.question(self, t("export.title"), t("export.text", files=files))
        if answer != QMessageBox.StandardButton.Yes:
            return
        default = str(Path.home() / default_zip_name(self.result))
        path, _filter = QFileDialog.getSaveFileName(self, t("export.dialog"), default, "ZIP (*.zip)")
        if not path:
            return
        try:
            build_zip(self.result, path, lang)
        except ClaudiosError as exc:
            show_error(self, error_info(exc))
            return
        QMessageBox.information(self, t("export.title"), t("export.saved", path=path))




class DocPage(QWidget):
    """Ein Dokument (Handbuch oder Technik-Doku): links das Inhaltsverzeichnis (eine Zeile je Prüfung), rechts der Text
    mit farbig hinterlegten Suchtreffern. Die Suche kann im Seitenkopf der Hilfe liegen (dann ist das eigene Feld aus)."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self._rendered: str | None = None
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.toc = QListWidget()
        self.toc.setObjectName("toc")
        self.toc.setFixedWidth(290)
        self.toc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.toc.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view = LinkText()
        self.view.setReadOnly(True)
        if mode == "tech":
            self.view.setFont(QFont("Menlo" if sys.platform == "darwin" else "Consolas", 10))
            self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.addWidget(self.toc)
        columns.addWidget(self.view, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.search)
        lay.addLayout(columns, 1)
        self.search.textChanged.connect(self.refresh)
        self.toc.currentRowChanged.connect(self._goto_row)

    def retranslate(self) -> None:
        self.search.setPlaceholderText(t("doc.search"))
        self.toc.setAccessibleName(t("doc.toc"))
        self.refresh()

    def refresh(self, *_args) -> None:
        query = self.search.text()
        self.view.setPlainText(render_doc(self.mode, get_lang(), query))
        self.view.set_marks([query.strip()] if query.strip() else [])
        self._rendered = query
        self._fill_toc()

    def refresh_if_stale(self) -> None:
        """Nach einem Wechsel des Reiters: neu zeichnen, wenn sich die Suche seit dem letzten Zeichnen geändert hat."""
        if self._rendered != self.search.text():
            self.refresh()

    def _fill_toc(self) -> None:
        """Inhaltsverzeichnis aus den Überschriften: die Zeile nach der Trennlinie (und einer Leerzeile) ist der Titel."""
        self.toc.blockSignals(True)
        self.toc.clear()
        block = self.view.document().begin()
        after_rule = False
        while block.isValid():
            text = block.text()
            if len(text) >= 20 and set(text) == {"-"}:
                after_rule = True
            elif text.strip() and after_rule:
                after_rule = False
                item = QListWidgetItem(text.strip())
                item.setToolTip(text.strip())
                item.setData(Qt.ItemDataRole.UserRole, block.position())
                self.toc.addItem(item)
            block = block.next()
        self.toc.blockSignals(False)

    def _goto_row(self, row: int) -> None:
        item = self.toc.item(row)
        if item is None:
            return
        position = int(item.data(Qt.ItemDataRole.UserRole))
        cursor = QTextCursor(self.view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.view.setTextCursor(cursor)  # erst ans Ende, dann zum Ziel: so steht der Eintrag oben im Fenster
        self.view.ensureCursorVisible()
        cursor.setPosition(position)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()


class SettingsPage(QWidget):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self._settings = settings
        self.localhost = QCheckBox()
        self.localhost.setChecked(bool(settings.get("allow_localhost")))
        self.warn = _plain(QLabel())
        self.warn.setObjectName("muted")
        self.updates = QCheckBox()
        self.updates.setChecked(settings.get("update_check") is not False)
        self.update_note = _plain(QLabel())
        self.update_note.setObjectName("muted")
        self.limits = _plain(QLabel())
        self.limits.setObjectName("muted")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.localhost)
        lay.addWidget(self.warn)
        lay.addSpacing(16)
        lay.addWidget(self.updates)
        lay.addWidget(self.update_note)
        lay.addSpacing(16)
        lay.addWidget(self.limits)
        lay.addStretch(1)
        self.localhost.toggled.connect(self._toggle)
        self.updates.toggled.connect(self._toggle_updates)

    def _toggle_updates(self, checked: bool) -> None:
        """Aus wird gespeichert, an ist der Normalfall (Schlüssel fehlt)."""
        if checked:
            self._settings.pop("update_check", None)
        else:
            self._settings["update_check"] = False
        save_settings(self._settings)

    def _toggle(self, checked: bool) -> None:
        self._settings["allow_localhost"] = checked
        save_settings(self._settings)

    def retranslate(self) -> None:
        self.localhost.setText(t("settings.localhost"))
        self.updates.setText(t("settings.updates"))
        self.update_note.setText(t("settings.updates_note"))
        self.warn.setText(t("settings.localhost_warn"))
        self.limits.setText(t("settings.limits", depth=n(LIMITS.max_depth), p1=n(LIMITS.pages_level1),
                              p2=n(LIMITS.pages_level2)))
