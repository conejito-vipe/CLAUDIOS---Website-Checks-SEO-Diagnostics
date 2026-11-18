"""Seite 'Externe Dienste': Schalter für Abfragen bei Dritten (nicht bei der geprüften Website). Alles ist standardmäßig
aus. Wird vom Hauptfenster automatisch gefunden."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox, QVBoxLayout, QWidget

from ..core import services
from ..i18n.strings import t
from .dialogs import error_info, show_error

NAV_KEY = "nav.services"


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _confirm(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("svc.title"), text) == QMessageBox.StandardButton.Yes


class ServicesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = _plain(QLabel())
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.rdap = QCheckBox()
        self.rdap_info = _plain(QLabel())
        self.rdap_info.setObjectName("muted")
        self.state = _plain(QLabel())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for widget in (self.title, self.intro, self.rdap, self.rdap_info, self.state):
            lay.addWidget(widget)
        lay.addStretch(1)
        self.rdap.toggled.connect(self._toggle_rdap)

    def retranslate(self) -> None:
        self.title.setText(t("svc.title"))
        self.intro.setText(t("svc.intro"))
        self.rdap.setText(t("svc.rdap.switch"))
        self.rdap_info.setText(t("svc.rdap.info"))
        self.refresh()

    def refresh(self) -> None:
        on = services.enabled("rdap")
        self.rdap.blockSignals(True)
        self.rdap.setChecked(on)
        self.rdap.blockSignals(False)
        self.state.setText(t("svc.state.on") if on else t("svc.state.off"))

    def _toggle_rdap(self, checked: bool) -> None:
        if checked and not _confirm(self, t("svc.rdap.ask")):
            self.refresh()
            return
        try:
            services.set_enabled("rdap", checked)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund gezeigt
            show_error(self, error_info(exc))
        self.refresh()


def create(window) -> ServicesPage:
    return ServicesPage()
