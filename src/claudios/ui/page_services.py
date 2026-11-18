"""Seite 'Externe Dienste': Schalter für Abfragen bei Dritten (nicht bei der geprüften Website), Schlüssel für Safe
Browsing und lokale Optionen (Screenshots). Alles ist standardmäßig aus. Wird vom Hauptfenster automatisch gefunden."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import apikeys, options, services
from ..i18n.strings import t
from ..report import shots
from .dialogs import error_info, show_error

NAV_KEY = "nav.services"


def _plain(label: QLabel) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def _confirm(parent, text: str) -> bool:
    return QMessageBox.question(parent, t("svc.title"), text) == QMessageBox.StandardButton.Yes


def _warn(parent, text: str) -> None:
    QMessageBox.warning(parent, t("svc.title"), text)


def _info(parent, text: str) -> None:
    QMessageBox.information(parent, t("svc.title"), text)


def _pick_zip(parent, default: str) -> str:
    path, _filter = QFileDialog.getSaveFileName(parent, t("svc.shots.dialog"), default, "ZIP (*.zip)")
    return path


class ServicesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result = None
        self.title = _plain(QLabel())
        self.intro = _plain(QLabel())
        self.intro.setObjectName("muted")
        self.rdap = QCheckBox()
        self.rdap_info = _plain(QLabel())
        self.rdap_info.setObjectName("muted")
        self.state = _plain(QLabel())
        self.sb = QCheckBox()
        self.sb_info = _plain(QLabel())
        self.sb_info.setObjectName("muted")
        self.sb_key = QLineEdit()
        self.sb_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.sb_save = QPushButton()
        self.sb_delete = QPushButton()
        self.sb_state = _plain(QLabel())
        self.psi = QCheckBox()
        self.psi_info = _plain(QLabel())
        self.psi_info.setObjectName("muted")
        self.local_title = _plain(QLabel())
        self.shots = QCheckBox()
        self.shots_info = _plain(QLabel())
        self.shots_info.setObjectName("muted")
        self.shots_btn = QPushButton()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for widget in (self.title, self.intro, self.rdap, self.rdap_info, self.state, self.sb, self.sb_info,
                       self.sb_key, self.sb_save, self.sb_delete, self.sb_state, self.psi, self.psi_info,
                       self.local_title, self.shots, self.shots_info, self.shots_btn):
            lay.addWidget(widget)
        lay.addStretch(1)
        self.rdap.toggled.connect(self._toggle_rdap)
        self.sb.toggled.connect(self._toggle_sb)
        self.psi.toggled.connect(self._toggle_psi)
        self.shots.toggled.connect(self._toggle_shots)
        self.sb_save.clicked.connect(self.save_key)
        self.sb_delete.clicked.connect(self.delete_key)
        self.shots_btn.clicked.connect(self.export_shots)

    def retranslate(self) -> None:
        self.title.setText(t("svc.title"))
        self.intro.setText(t("svc.intro"))
        self.rdap.setText(t("svc.rdap.switch"))
        self.rdap_info.setText(t("svc.rdap.info"))
        self.sb.setText(t("svc.sb.switch"))
        self.sb_info.setText(t("svc.sb.info"))
        self.sb_key.setPlaceholderText(t("svc.sb.key_ph"))
        self.sb_save.setText(t("svc.sb.save"))
        self.sb_delete.setText(t("svc.sb.delete"))
        self.psi.setText(t("svc.psi.switch"))
        self.psi_info.setText(t("svc.psi.info"))
        self.local_title.setText(t("svc.local.title"))
        self.shots.setText(t("svc.shots.switch"))
        self.shots_info.setText(t("svc.shots.info"))
        self.shots_btn.setText(t("svc.shots.zip"))
        self.refresh()

    def refresh(self) -> None:
        for box, on in ((self.rdap, services.enabled("rdap")), (self.sb, services.enabled("safebrowsing")),
                        (self.psi, services.enabled("pagespeed")), (self.shots, options.enabled("screenshots"))):
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)
        self.state.setText(t("svc.state.on") if services.enabled("rdap") else t("svc.state.off"))
        try:
            has, persistent = apikeys.has_key("safebrowsing"), apikeys.persistent()
        except Exception:  # noqa: BLE001 – ein Speicherfehler heißt nur: kein Schlüssel angezeigt
            has, persistent = False, False
        text = t("svc.sb.saved") if has else t("svc.sb.none")
        self.sb_state.setText(f"{text} {t('svc.sb.memory')}" if has and not persistent else text)
        self.sb_delete.setEnabled(has)
        self.shots_btn.setEnabled(self.result is not None)

    def _switch(self, name: str, checked: bool, ask_key: str, local: bool = False) -> None:
        if checked and not _confirm(self, t(ask_key)):
            self.refresh()
            return
        try:
            (options if local else services).set_enabled(name, checked)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird mit Grund gezeigt
            show_error(self, error_info(exc))
        self.refresh()

    def _toggle_rdap(self, checked: bool) -> None:
        self._switch("rdap", checked, "svc.rdap.ask")

    def _toggle_sb(self, checked: bool) -> None:
        self._switch("safebrowsing", checked, "svc.sb.ask")

    def _toggle_psi(self, checked: bool) -> None:
        self._switch("pagespeed", checked, "svc.psi.ask")

    def _toggle_shots(self, checked: bool) -> None:
        self._switch("screenshots", checked, "svc.shots.ask", local=True)

    def save_key(self) -> None:
        try:
            apikeys.set_key("safebrowsing", self.sb_key.text())
        except ValueError:
            _warn(self, t("svc.sb.invalid"))
            return
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
            return
        self.sb_key.clear()
        self.refresh()

    def delete_key(self) -> None:
        try:
            apikeys.delete("safebrowsing")
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
        self.refresh()

    def show_result(self, result) -> None:
        self.result = result
        self.refresh()

    def export_shots(self) -> None:
        if self.result is None or not shots.files_of(self.result):
            _info(self, t("svc.shots.none"))
            return
        path = _pick_zip(self, str(Path.home() / shots.default_name(self.result)))
        if not path:
            return
        try:
            shots.build_zip(self.result, path)
        except Exception as exc:  # noqa: BLE001
            show_error(self, error_info(exc))
            return
        _info(self, t("export.saved", path=path))


def create(window) -> ServicesPage:
    page = ServicesPage()
    signal = getattr(getattr(window, "scan", None), "scan_finished", None)
    if signal is not None:
        signal.connect(page.show_result)
    return page
