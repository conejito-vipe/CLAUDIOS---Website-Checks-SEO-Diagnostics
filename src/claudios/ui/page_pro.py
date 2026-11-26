"""Seite 'Pro und Lizenz': zeigt Lizenz und Schaltdatei der Verwaltung (CONEJITO Admin) und nimmt beides entgegen.
Ausgeliefert inaktiv (angebot.AKTIV falsch): kein Navigationseintrag, alle Bedienelemente aus. Wird vom Hauptfenster
automatisch gefunden."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import angebot, lizenz, schalt
from ..i18n.strings import n, t
from ..paths import data_dir

NAV_KEY = "nav.pro"


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _reason(reason: str) -> str:
    key = f"pro.reason.{reason}"
    text = t(key)
    return reason if text == key else text


class ProPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = _plain(QLabel())
        self.banner = _plain(QLabel())
        self.banner.setObjectName("muted")
        self.lic_head, self.lic_status, self.lic_note = (_plain(QLabel()) for _ in range(3))
        self.lic_head.setObjectName("h2")
        self.lic_note.setObjectName("muted")
        self.key_input = QLineEdit()
        self.save_btn, self.remove_btn = QPushButton(), QPushButton()
        self.sw_head, self.sw_status, self.sw_note = (_plain(QLabel()) for _ in range(3))
        self.sw_head.setObjectName("h2")
        self.sw_note.setObjectName("muted")
        self.file_btn, self.fetch_btn = QPushButton(), QPushButton()
        self.cmp_head = _plain(QLabel())
        self.cmp_head.setObjectName("h2")
        self.table = QTableWidget(0, 3)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.save_btn.clicked.connect(self.save_key)
        self.remove_btn.clicked.connect(self.remove_key)
        self.file_btn.clicked.connect(self.load_file)
        self.fetch_btn.clicked.connect(self.fetch)
        self.message = lambda text: None  # vom Test oder Hauptfenster ersetzbar
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        for widget in (self.title, self.banner):
            lay.addWidget(widget)
        for block in ((self.lic_head, self.lic_status, self.key_input, self.save_btn, self.remove_btn, self.lic_note),
                      (self.sw_head, self.sw_status, self.file_btn, self.fetch_btn, self.sw_note)):
            frame = QFrame()
            frame.setObjectName("panel")
            inner = QVBoxLayout(frame)
            for widget in block:
                inner.addWidget(widget)
            lay.addWidget(frame)
        lay.addWidget(self.cmp_head)
        lay.addWidget(self.table, 1)

    @property
    def base(self):
        return data_dir()

    def retranslate(self) -> None:
        active = angebot.AKTIV
        self.title.setText(t("pro.title"))
        self.banner.setText("" if active else t("pro.inactive"))
        self.banner.setVisible(not active)
        self.lic_head.setText(t("pro.lic.title"))
        self.key_input.setPlaceholderText(t("pro.lic.placeholder"))
        self.save_btn.setText(t("pro.lic.save"))
        self.remove_btn.setText(t("pro.lic.remove"))
        self.sw_head.setText(t("pro.sw.title"))
        self.file_btn.setText(t("pro.sw.file"))
        self.fetch_btn.setText(t("pro.sw.fetch"))
        self.cmp_head.setText(t("pro.cmp.title"))
        self.table.setHorizontalHeaderLabels([t("pro.cmp.feature"), t("pro.cmp.normal"), t("pro.cmp.pro")])
        self.table.setRowCount(0)
        for feature in angebot.FEATURES:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = (t(f"pro.f.{feature['id']}"), "✓" if feature["normal"] else "–", "✓" if feature["pro"] else "–")
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.refresh()

    def refresh(self) -> None:
        active = angebot.AKTIV
        lic = lizenz.state(self.base)
        if not lic["has_key"]:
            self.lic_status.setText(t("pro.lic.none"))
        elif lic["valid"]:
            self.lic_status.setText(t("pro.lic.ok", name=lic["name"], art=lic["art"], until=lic["until"]))
        else:
            self.lic_status.setText(t("pro.lic.bad", reason=_reason(lic.get("reason", ""))))
        notes = [t("pro.lic.warn", days=n(lic["days_left"]))] if lic.get("warn_expiry") else []
        if not lic["public_key_set"]:
            notes.append(t("pro.lic.nokey"))
        self.lic_note.setText(" ".join(notes))
        data = schalt.load(self.base)
        if data is None:
            self.sw_status.setText(t("pro.sw.none"))
        else:
            self.sw_status.setText(t("pro.sw.state", serial=n(data["serial"]), seit=data["seit"],
                                     mode=t("pro.sw.on" if data["aktiv"] else "pro.sw.off"),
                                     blocked=n(len(data["gesperrt"]))))
        self.sw_note.setText("" if schalt.SCHALT_URL else t("pro.sw.nourl"))
        for widget in (self.key_input, self.save_btn, self.remove_btn, self.file_btn):
            widget.setEnabled(active)
        self.fetch_btn.setEnabled(active and bool(schalt.SCHALT_URL))
        self.remove_btn.setEnabled(active and lic["has_key"])

    def save_key(self) -> None:
        res = lizenz.store(self.base, self.key_input.text())
        if res["valid"] or res.get("reason") == "abgelaufen":
            self.key_input.clear()
        self.refresh()

    def remove_key(self) -> None:
        lizenz.remove(self.base)
        self.refresh()

    def _report(self, result: dict) -> None:
        self.message(t("pro.sw.ok") if result["ok"] else t("pro.sw.fail", reason=result["reason"]))
        self.refresh()

    def load_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, t("pro.sw.file"), "", "Text (*.txt)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read(schalt.MAX_LEN + 10)
        except OSError:
            self._report({"ok": False, "reason": "nicht lesbar"})
            return
        why = schalt.accept(self.base, text)
        self._report({"ok": not why, "reason": why})

    def fetch(self) -> None:
        self._report(schalt.refresh(self.base))


def create(window) -> ProPage:
    schalt.apply(data_dir())  # gespeicherte Sperrliste und Lizenzpflicht beim Start übernehmen
    return ProPage()
