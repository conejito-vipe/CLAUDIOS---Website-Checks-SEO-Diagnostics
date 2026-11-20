"""Zentrale Fehleranzeige (immer mit Grund, im Stil des Splash) und Info-Dialog."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton

from .. import REPO_URL, __version__
from ..buildinfo import python_lines
from ..core.errors import ClaudiosError, ErrorCode, describe
from ..i18n.strings import get_lang, n, t
from ..paths import LOG_NAME, logs_dir
from .cardbox import MARGIN, CardDialog, MessageCard
from .logfolder import open_logs


def error_info(exc: BaseException) -> dict[str, str]:
    lang = get_lang()
    if isinstance(exc, ClaudiosError):
        return describe(exc.code, lang, **exc.ctx)
    return describe(ErrorCode.INTERNAL, lang, reason=type(exc).__name__)


def error_card(parent, info: dict[str, str]) -> MessageCard:
    """Baut den Fehlerdialog (Code und Zeit zum Kopieren, Ort der Protokolldatei, Knopf zum Protokollordner)."""
    stamp = datetime.now().isoformat(timespec="seconds")
    footnote = f"{info['code']} · {stamp}\n{t('card.logs', path=logs_dir() / LOG_NAME)}"
    text = f"{info['cause']}\n\n{t('err.todo')} {info['action']}"
    return MessageCard(parent, "warning", info["title"], text, footnote=footnote,
                       extra=(t("card.open_logs"), open_logs))


def show_error(parent, info: dict[str, str]) -> None:
    error_card(parent, info).run()


class AboutDialog(CardDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent, t("about.title"))
        self.resize(2 * MARGIN + 560, 2 * MARGIN + 520)
        heading = QLabel(t("about.title"))
        heading.setObjectName("h1")
        self.content.addWidget(heading)
        info = QLabel(t("about.text", version=__version__, lines=n(python_lines()), repo=REPO_URL))
        info.setTextFormat(Qt.TextFormat.PlainText)
        info.setWordWrap(True)
        self.content.addWidget(info)
        notices = QPlainTextEdit(t("about.licenses"))
        notices.setReadOnly(True)
        self.content.addWidget(notices, 1)
        close = QPushButton(t("about.close"))
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        self.content.addWidget(close)
