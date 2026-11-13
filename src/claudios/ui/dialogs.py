"""Zentrale Fehleranzeige (immer mit Grund) und About-Dialog."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout

from .. import REPO_URL, __version__
from ..buildinfo import python_lines
from ..core.errors import ClaudiosError, ErrorCode, describe
from ..i18n.strings import get_lang, n, t


def error_info(exc: BaseException) -> dict[str, str]:
    lang = get_lang()
    if isinstance(exc, ClaudiosError):
        return describe(exc.code, lang, **exc.ctx)
    return describe(ErrorCode.INTERNAL, lang, reason=type(exc).__name__)


def show_error(parent, info: dict[str, str]) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setTextFormat(Qt.TextFormat.PlainText)  # Inhalte von geprüften Seiten nie als Rich-Text deuten
    box.setWindowTitle(info["code"])
    box.setText(info["title"])
    box.setInformativeText(f"{info['cause']}\n\n{t('err.todo')} {info['action']}")
    box.setDetailedText(f"{info['code']}\n{datetime.now().isoformat(timespec='seconds')}")
    box.exec()


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("about.title"))
        self.resize(560, 460)
        lay = QVBoxLayout(self)
        info = QLabel(t("about.text", version=__version__, lines=n(python_lines()), repo=REPO_URL))
        info.setTextFormat(Qt.TextFormat.PlainText)
        info.setWordWrap(True)
        lay.addWidget(info)
        notices = QPlainTextEdit(t("about.licenses"))
        notices.setReadOnly(True)
        lay.addWidget(notices, 1)
        close = QPushButton(t("about.close"))
        close.clicked.connect(self.accept)
        lay.addWidget(close)
