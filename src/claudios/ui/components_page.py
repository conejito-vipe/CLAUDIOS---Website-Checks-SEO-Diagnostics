"""Seite „Komponenten": Version, Download, belegter Platz und Status (✅ oder ❌), Installieren/Reparieren, Entfernen."""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..components import info, manager
from ..components.lock import load_lock
from ..core.numfmt import format_bytes
from ..i18n.strings import get_lang, n, t
from .dialogs import error_info, show_error
from .logfolder import open_logs

STATE_ICONS = {"installed": "✅", "missing": "❌", "outdated": "🔄", "not_pinned": "⚠️"}


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class InstallThread(QThread):
    progress = Signal(str, str, int, int)
    done = Signal(object)

    def __init__(self, comps: list) -> None:
        super().__init__()
        self._comps = comps
        self._cancel = threading.Event()

    def run(self) -> None:
        results = []
        for comp in self._comps:
            if self._cancel.is_set():
                break
            try:
                manager.install(comp, progress=lambda name, phase, d, total: self.progress.emit(name, phase, d, total),
                                cancel=self._cancel)
                results.append((comp.name, None))
            except Exception as exc:  # noqa: BLE001 – jeder Fehler wird dem Nutzer mit Grund gezeigt
                results.append((comp.name, exc))
        self.done.emit(results)

    def cancel(self) -> None:
        self._cancel.set()


class UninstallDialog(QDialog):
    def __init__(self, parent, items: list, lock: list) -> None:
        super().__init__(parent)
        self._lock = lock
        self.setWindowTitle(t("unin.title"))
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        intro = _plain(QLabel(t("unin.intro")))
        lay.addWidget(intro)
        lang = get_lang()
        self._boxes: dict[str, QCheckBox] = {}
        for item in items:
            if item.kind == "tool":
                label = item.title
            else:
                label_key = "unin.item." + item.key
                label = t(label_key)
            box = QCheckBox(f"{label} ({format_bytes(item.size, lang)})")
            box.setChecked(item.default)
            box.toggled.connect(self._update)
            lay.addWidget(box)
            self._boxes[item.key] = box
        self.warn = _plain(QLabel())
        lay.addWidget(self.warn)
        note = _plain(QLabel(t("unin.audit_note")))
        note.setObjectName("muted")
        lay.addWidget(note)
        lay.addStretch(1)
        ok = QPushButton(t("unin.ok"))
        ok.setObjectName("primary")
        cancel = QPushButton(t("unin.cancel"))
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        lay.addWidget(ok)
        lay.addWidget(cancel)
        self._update()

    def selected(self) -> list[str]:
        return [key for key, box in self._boxes.items() if box.isChecked()]

    def _update(self, *_args) -> None:
        names = [key[5:] for key in self.selected() if key.startswith("tool:")]
        if not names:
            self.warn.setText("")
            return
        deps = manager.dependents(names, self._lock)
        count = manager.affected_checks(names, self._lock)
        self.warn.setText(t("unin.warn_dep", count=n(count), names=", ".join(deps) or "–"))


class ComponentsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread: InstallThread | None = None
        self._lock: list = []
        self._lock_error = ""
        try:
            self._lock = load_lock()
        except (ValueError, KeyError, OSError) as exc:
            self._lock_error = type(exc).__name__
        self.intro = _plain(QLabel())
        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.total = _plain(QLabel())
        self.total.setObjectName("muted")
        self.hint = _plain(QLabel())
        self.hint.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.status = _plain(QLabel())
        self.install_btn = QPushButton()
        self.install_btn.setObjectName("primary")
        self.cancel_btn = QPushButton()
        self.cancel_btn.setEnabled(False)
        self.remove_btn = QPushButton()
        self.logs_btn = QPushButton()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for widget in (self.intro, self.table, self.total, self.hint, self.bar, self.status,
                       self.install_btn, self.cancel_btn, self.remove_btn, self.logs_btn):
            lay.addWidget(widget)
        self.install_btn.clicked.connect(self.install)
        self.cancel_btn.clicked.connect(self.cancel)
        self.remove_btn.clicked.connect(self.remove)
        self.logs_btn.clicked.connect(lambda _checked=False: open_logs())

    def retranslate(self) -> None:
        self.intro.setText(t("cmp.intro"))
        self.table.setHorizontalHeaderLabels([t("cmp.col.name"), t("cmp.col.version"), t("cmp.col.download"),
                                              t("cmp.col.disk"), t("cmp.col.status")])
        self.install_btn.setText(t("cmp.install"))
        self.cancel_btn.setText(t("cmp.cancel"))
        self.remove_btn.setText(t("cmp.uninstall"))
        self.logs_btn.setText(t("card.open_logs"))
        self.refresh()

    def refresh(self) -> None:
        lang = get_lang()
        self.table.setRowCount(0)
        unpinned = False
        used = 0
        for comp in self._lock:
            state = manager.status(comp)
            unpinned = unpinned or state == "not_pinned"
            disk = info.disk_size(comp) if state in ("installed", "outdated") else 0
            used += disk
            download, approx = info.download_size_of(comp)
            if not download:
                download_text = "–"
            elif approx:
                download_text = t("cmp.approx", size=format_bytes(download, lang))
            else:
                download_text = format_bytes(download, lang)
            row = self.table.rowCount()
            self.table.insertRow(row)
            state_key = "cmp.st." + state
            cells = (comp.title, info.version_of(comp) or "–", download_text,
                     format_bytes(disk, lang) if disk else "–", STATE_ICONS.get(state, "❔"))
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(t(state_key))
                elif col in (2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()
        self.total.setText(t("cmp.total2", size=format_bytes(used, lang)))
        if self._lock_error:
            self.hint.setText(t("cmp.lock_error", reason=self._lock_error))
        else:
            self.hint.setText(t("cmp.unpinned_hint") if unpinned else "")

    def _pending(self) -> list:
        return [c for c in self._lock if manager.status(c) in ("missing", "outdated")]

    def install(self) -> None:
        if self._thread is not None:
            return
        pending = self._pending()
        if not pending:
            self.status.setText(t("cmp.nothing"))
            return
        thread = InstallThread(pending)
        thread.progress.connect(self._on_progress)
        thread.done.connect(self._on_done)
        thread.finished.connect(self._cleanup)
        self._thread = thread
        self.install_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        thread.start()

    def cancel(self) -> None:
        if self._thread is not None:
            self._thread.cancel()
            self.cancel_btn.setEnabled(False)

    def shutdown(self) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.cancel()
            thread.wait(20000)

    def _on_progress(self, name: str, phase: str, done: int, total: int) -> None:
        percent = int(done / total * 100) if total else 0
        phase_key = "cmp.phase." + phase
        self.bar.setValue(percent)
        self.status.setText(t("cmp.working", name=name, phase=t(phase_key), percent=n(percent)))

    def _on_done(self, results: list) -> None:
        failures = [(name, exc) for name, exc in results if exc is not None]
        self.status.setText(t("cmp.done", ok=n(len(results) - len(failures)), failed=n(len(failures))))
        self.bar.setValue(0)
        self.refresh()
        if failures:
            show_error(self, error_info(failures[0][1]))

    def _cleanup(self) -> None:
        self._thread = None
        self.install_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def remove(self) -> None:
        if self._thread is not None:
            return
        items = manager.uninstall_items(self._lock)
        if not items:
            QMessageBox.information(self, t("unin.title"), t("unin.empty"))
            return
        dialog = UninstallDialog(self, items, self._lock)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected():
            return
        if QMessageBox.question(self, t("unin.title"), t("unin.confirm")) != QMessageBox.StandardButton.Yes:
            return
        result = manager.uninstall(dialog.selected(), self._lock)
        failed = [key for key, error in result.items() if error]
        details = f"{', '.join(failed)}. {t('unin.hint_failed')}" if failed else ""
        QMessageBox.information(self, t("unin.title"),
                                t("unin.done", ok=n(len(result) - len(failed)), failed=n(len(failed)),
                                  details=details))
        self.refresh()
