"""Seite „Komponenten“: Status, Installieren/Reparieren und Entfernen mit Auswahl."""
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

from ..components import manager
from ..components.lock import load_lock
from ..core.numfmt import format_bytes
from ..i18n.strings import get_lang, n, t
from .dialogs import error_info, show_error


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
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for widget in (self.intro, self.table, self.total, self.hint, self.bar, self.status,
                       self.install_btn, self.cancel_btn, self.remove_btn):
            lay.addWidget(widget)
        self.install_btn.clicked.connect(self.install)
        self.cancel_btn.clicked.connect(self.cancel)
        self.remove_btn.clicked.connect(self.remove)

    def retranslate(self) -> None:
        self.intro.setText(t("cmp.intro"))
        self.table.setHorizontalHeaderLabels(
            [t("cmp.col.name"), t("cmp.col.version"), t("cmp.col.size"), t("cmp.col.status")])
        self.install_btn.setText(t("cmp.install"))
        self.cancel_btn.setText(t("cmp.cancel"))
        self.remove_btn.setText(t("cmp.uninstall"))
        self.refresh()

    def refresh(self) -> None:
        lang = get_lang()
        self.table.setRowCount(0)
        unpinned = False
        for comp in self._lock:
            state = manager.status(comp)
            unpinned = unpinned or state == "not_pinned"
            row = self.table.rowCount()
            self.table.insertRow(row)
            state_key = "cmp.st." + state
            cells = (comp.title, comp.version or "–", format_bytes(comp.size, lang) if comp.size else "–",
                     t(state_key))
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(value))
        used = sum(item.size for item in manager.uninstall_items(self._lock) if item.kind == "tool")
        self.total.setText(t("cmp.total", size=format_bytes(used, lang)))
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