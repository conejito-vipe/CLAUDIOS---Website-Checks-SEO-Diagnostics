"""Karten-Dialoge im Stil des Splash: rahmenlos, abgerundete Karte mit Schatten und eigener Titelleiste.

CardDialog ist die Basis (auch für den Info-Dialog). MessageCard ersetzt die Qt-Standardmeldungen. install() leitet
QMessageBox.information/warning/critical/question auf MessageCard um, damit auch Seiten ohne Änderung den neuen Stil
bekommen. install() wird nur im echten Programm aufgerufen (app.py), nicht in Tests."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..i18n.strings import t
from .widgets import MARGIN, TitleBar

SB = QMessageBox.StandardButton

ICONS = {
    "info": ("i", "#2B7CD0"),
    "question": ("?", "#EE6A12"),
    "warning": ("!", "#E0A100"),
    "error": ("✕", "#C62828"),
}
# (Schaltfläche, Schlüssel, Textschlüssel) in der Reihenfolge der Anzeige
BUTTON_KEYS = (
    (SB.Ok, "ok", "card.ok"),
    (SB.Yes, "yes", "card.yes"),
    (SB.No, "no", "card.no"),
    (SB.Cancel, "cancel", "card.cancel"),
    (SB.Close, "close", "card.close"),
)


def _val(item) -> int:
    return int(getattr(item, "value", item))


def _has(buttons, flag) -> bool:
    return bool(_val(buttons) & _val(flag))


class CardDialog(QDialog):
    """Rahmenloser Dialog. Inhalt kommt in self.content (QVBoxLayout)."""

    def __init__(self, parent=None, title: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("carddialog")
        self.setStyleSheet("QDialog#carddialog { background: transparent; }")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowTitle(title)
        self._placed = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.titlebar = TitleBar(False)
        self.titlebar.btn_min.setVisible(False)
        self.body.addWidget(self.titlebar)
        self.content = QVBoxLayout()
        self.content.setContentsMargins(24, 8, 24, 20)
        self.content.setSpacing(12)
        self.body.addLayout(self.content, 1)

    def _center(self) -> None:
        frame = self.frameGeometry()
        parent = self.parentWidget()
        anchor = parent.window() if parent is not None else None
        if anchor is not None and anchor.isVisible():
            frame.moveCenter(anchor.frameGeometry().center())
        else:
            screen = self.screen()
            if screen is None:
                return
            frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().showEvent(event)
        if not self._placed:
            self._placed = True
            self._center()


def _plain(label: QLabel, selectable: bool = False) -> QLabel:
    label.setTextFormat(Qt.TextFormat.PlainText)  # Inhalte von geprüften Seiten nie als Rich-Text deuten
    label.setWordWrap(True)
    if selectable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class MessageCard(CardDialog):
    def __init__(self, parent, kind: str, title: str, text: str, *, buttons=SB.Ok, default=None,
                 footnote: str = "", details: str = "") -> None:
        super().__init__(parent, title)
        self.setMinimumWidth(2 * MARGIN + 480)
        self.chosen = SB.NoButton
        glyph, color = ICONS.get(kind, ICONS["info"])
        icon = QLabel(glyph)
        icon.setFixedSize(44, 44)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"background: {color}; color: white; border-radius: 22px; "
                           "font-size: 22px; font-weight: 700;")
        column = QVBoxLayout()
        column.setSpacing(8)
        if title:
            heading = _plain(QLabel(title))
            heading.setObjectName("h2")
            column.addWidget(heading)
        if text:
            column.addWidget(_plain(QLabel(text), selectable=True))
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(column, 1)
        self.content.addLayout(row)
        if footnote:
            note = _plain(QLabel(footnote), selectable=True)
            note.setObjectName("muted")
            self.content.addWidget(note)
        self.details_box: QPlainTextEdit | None = None
        self.details_btn: QPushButton | None = None
        if details:
            self.details_btn = QPushButton(t("card.details"))
            self.details_btn.clicked.connect(self._toggle)
            self.details_box = QPlainTextEdit(details)
            self.details_box.setReadOnly(True)
            self.details_box.setMaximumHeight(110)
            self.details_box.setVisible(False)
            self.content.addWidget(self.details_btn, 0, Qt.AlignmentFlag.AlignLeft)
            self.content.addWidget(self.details_box)

        shown = [(flag, key, label) for flag, key, label in BUTTON_KEYS if _has(buttons, flag)]
        if not shown:
            shown = [BUTTON_KEYS[0]]
        default_flag = next((flag for flag, _k, _l in shown if default is not None and _val(flag) == _val(default)),
                            shown[0][0])
        self._escape = next((flag for flag, key, _l in shown if key in ("cancel", "no", "close")), shown[0][0])
        self.buttons: dict[str, QPushButton] = {}
        line = QHBoxLayout()
        line.addStretch(1)
        for flag, key, label in shown:
            btn = QPushButton(t(label))
            btn.setAutoDefault(False)
            if _val(flag) == _val(default_flag):
                btn.setObjectName("primary")
                btn.setDefault(True)
                btn.setFocus()
            btn.clicked.connect(lambda _checked=False, f=flag: self._pick(f))
            line.addWidget(btn)
            self.buttons[key] = btn
        self.content.addLayout(line)

    def _toggle(self) -> None:
        if self.details_box is None or self.details_btn is None:
            return
        show = self.details_box.isHidden()
        self.details_box.setVisible(show)
        self.details_btn.setText(t("card.details_hide" if show else "card.details"))
        self.adjustSize()

    def _pick(self, flag) -> None:
        self.chosen = flag
        self.accept()

    def reject(self) -> None:
        if _val(self.chosen) == 0:
            self.chosen = self._escape
        super().reject()

    def run(self):
        self.exec()
        return self.chosen


def show_message(parent, kind: str, title: str, text: str, *, footnote: str = "", details: str = "") -> None:
    MessageCard(parent, kind, title, text, footnote=footnote, details=details).run()


def _ask(kind, parent, title, text, buttons, default):
    return MessageCard(parent, kind, title, text, buttons=buttons,
                       default=default if _val(default) else None).run()


def information(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
    return _ask("info", parent, title, text, buttons, defaultButton)


def warning(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
    return _ask("warning", parent, title, text, buttons, defaultButton)


def critical(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
    return _ask("error", parent, title, text, buttons, defaultButton)


def question(parent, title, text, buttons=SB.Yes | SB.No, defaultButton=SB.NoButton):
    return _ask("question", parent, title, text, buttons, defaultButton)


def install() -> None:
    """Leitet die statischen QMessageBox-Funktionen auf die Karten-Dialoge um."""
    QMessageBox.information = staticmethod(information)
    QMessageBox.warning = staticmethod(warning)
    QMessageBox.critical = staticmethod(critical)
    QMessageBox.question = staticmethod(question)
