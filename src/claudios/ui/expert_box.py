"""Experteneinstellungen im Scan-Bereich: Schalter für externe Dienste und Screenshots. Dieselben Schalter wie auf der Seite
'Externe Dienste' (core/services.py, core/options.py). Alles ist standardmäßig aus; jedes Einschalten fragt nach. Vor
jedem Scan fragt die Scan-Seite zusätzlich, wenn ein externer Dienst an ist."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..core import apikeys, options, services
from ..i18n.strings import t
from .cardbox import MARGIN, CardDialog
from .dialogs import error_info, show_error

SWITCHES = (("rdap", "rdap", "svc.rdap.ask", False), ("sb", "safebrowsing", "svc.sb.ask", False),
            ("psi", "pagespeed", "svc.psi.ask", False), ("ct", "crtsh", "svc.ct.ask", False), ("shots", "screenshots", "svc.shots.ask", True))


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _confirm(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("svc.title"), text) == QMessageBox.StandardButton.Yes


class ExpertDialog(CardDialog):
    """Die Experteneinstellungen in einem eigenen Fenster: es schließt mit „OK“ oder dem Schließen-Knopf."""

    def __init__(self, parent, body: QWidget) -> None:
        super().__init__(parent, t("expert.title"))
        self.resize(2 * MARGIN + 560, 2 * MARGIN + 460)
        self.heading = QLabel()
        self.heading.setObjectName("h1")
        self.content.addWidget(self.heading)
        self.content.addWidget(body, 1)
        self.ok = QPushButton()
        self.ok.setObjectName("primary")
        self.ok.clicked.connect(self.accept)
        self.content.addWidget(self.ok)

    def retranslate(self) -> None:
        self.setWindowTitle(t("expert.title"))
        self.heading.setText(t("expert.title"))
        self.ok.setText(t("expert.ok"))


class ExpertBox(QWidget):
    def __init__(self, open_services=None) -> None:
        super().__init__()
        self._open = open_services
        self.toggle = QPushButton()
        self.body = QWidget()
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.rdap, self.sb, self.psi, self.ct, self.shots = (QCheckBox(), QCheckBox(), QCheckBox(), QCheckBox(),
                                                            QCheckBox())
        self.hint = _plain(QLabel())
        self.hint.setObjectName("muted")
        self.keys_btn = QPushButton()
        inner = QVBoxLayout(self.body)
        inner.setContentsMargins(12, 0, 0, 0)
        for widget in (self.intro, self.rdap, self.sb, self.psi, self.ct, self.shots, self.hint, self.keys_btn):
            inner.addWidget(widget)
        self.dialog = ExpertDialog(self, self.body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.toggle)
        self.toggle.clicked.connect(self.open_dialog)
        self.keys_btn.clicked.connect(self._open_services)
        for attr, name, ask, local in SWITCHES:
            getattr(self, attr).toggled.connect(
                lambda checked, n=name, a=ask, loc=local: self._switch(n, a, loc, checked))

    def open_dialog(self) -> None:
        self.refresh()
        self.dialog.exec()

    def _open_services(self) -> None:
        self.dialog.accept()  # erst das Fenster schließen, dann zur Seite „Externe Dienste“
        if self._open is not None:
            self._open()

    def _title(self) -> None:
        self.toggle.setText(t("expert.open"))

    def retranslate(self) -> None:
        self._title()
        self.dialog.retranslate()
        self.intro.setText(t("scan.expert.intro"))
        self.rdap.setText(t("svc.rdap.switch"))
        self.sb.setText(t("svc.sb.switch"))
        self.psi.setText(t("svc.psi.switch"))
        self.ct.setText(t("svc.ct.switch"))
        self.shots.setText(t("svc.shots.switch"))
        self.keys_btn.setText(t("scan.expert.keys"))
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().showEvent(event)
        self.refresh()

    def _enabled(self, name: str, local: bool) -> bool:
        return options.enabled(name) if local else services.enabled(name)

    def refresh(self) -> None:
        for attr, name, _ask, local in SWITCHES:
            box = getattr(self, attr)
            box.blockSignals(True)
            box.setChecked(self._enabled(name, local))
            box.blockSignals(False)
        self.hint.setText(self._hint())
        self.hint.setVisible(bool(self.hint.text()))

    def _hint(self) -> str:
        lines = []
        try:
            if services.enabled("safebrowsing") and not apikeys.has_key("safebrowsing"):
                lines.append(t("scan.expert.nokey_sb"))
            if services.enabled("pagespeed") and not apikeys.has_key("pagespeed"):
                lines.append(t("scan.expert.nokey_psi"))
        except Exception:  # noqa: BLE001 – ein Speicherfehler heißt nur: kein Hinweis
            return ""
        return "\n".join(lines)

    def _switch(self, name: str, ask: str, local: bool, checked: bool) -> None:
        if checked and not _confirm(self, t(ask)):
            self.refresh()
            return
        try:
            (options if local else services).set_enabled(name, checked)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund gezeigt
            show_error(self, error_info(exc))
        self.refresh()

    def external_names(self) -> list[str]:
        """Namen der eingeschalteten Dienste, die bei diesem Scan Daten an Dritte senden würden."""
        names = []
        try:
            if services.enabled("rdap"):
                names.append(t("probe.rdap"))
            if services.enabled("safebrowsing") and apikeys.has_key("safebrowsing"):
                names.append(t("probe.safebrowsing"))
            if services.enabled("pagespeed"):
                names.append(t("probe.psi"))
            if services.enabled("crtsh"):
                names.append(t("probe.crtsh"))
        except Exception:  # noqa: BLE001
            return names
        return names
