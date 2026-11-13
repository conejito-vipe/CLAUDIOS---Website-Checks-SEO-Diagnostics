"""Gemeinsame Bausteine: rahmenloses Fenster mit Schatten, Titelleiste, Footer mit gezeichnetem Herz."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from ..buildinfo import python_lines
from ..i18n.strings import n, t
from ..paths import assets_dir


def load_logo() -> QPixmap | None:
    folder = assets_dir()
    if folder is not None:
        path = folder / "logo-full.png"
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                return pix
    return None


def load_icon() -> QIcon | None:
    folder = assets_dir()
    if folder is not None:
        for name in ("logo-icon.png", "logo-full.png"):
            path = folder / name
            if path.is_file():
                return QIcon(str(path))
    return None


class TitleBar(QWidget):
    langChanged = Signal(str)

    def __init__(self, with_lang: bool) -> None:
        super().__init__()
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 12, 0)
        self.pill = QLabel("Claudios")
        self.pill.setObjectName("pill")
        lay.addWidget(self.pill)
        lay.addStretch(1)
        self._lang_buttons: dict[str, QPushButton] = {}
        if with_lang:
            group = QButtonGroup(self)
            group.setExclusive(True)
            for code in ("de", "en"):
                btn = QPushButton(code.upper())
                btn.setObjectName("langbtn")
                btn.setCheckable(True)
                btn.clicked.connect(lambda _checked=False, c=code: self.langChanged.emit(c))
                group.addButton(btn)
                lay.addWidget(btn)
                self._lang_buttons[code] = btn
        self.btn_min = QPushButton("–")
        self.btn_close = QPushButton("✕")
        for btn in (self.btn_min, self.btn_close):
            btn.setObjectName("winbtn")
            lay.addWidget(btn)
        self.btn_min.clicked.connect(self._minimize)
        self.btn_close.clicked.connect(self._close)

    def _minimize(self) -> None:
        self.window().showMinimized()

    def _close(self) -> None:
        self.window().close()

    def set_lang(self, lang: str) -> None:
        btn = self._lang_buttons.get(lang)
        if btn is not None:
            btn.setChecked(True)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)


class CardWindow(QWidget):
    """Rahmenloses Fenster: abgerundete Karte mit Schatten und eigener Titelleiste."""

    def __init__(self, with_lang: bool) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
                            | Qt.WindowType.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
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
        self.titlebar = TitleBar(with_lang)
        self.body.addWidget(self.titlebar)


class HeartWidget(QWidget):
    """Das Herz wird gezeichnet statt als Emoji, damit es auf jedem Windows gleich aussieht."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(14, 14)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.moveTo(7, 13)
        path.cubicTo(-3, 6, 2, -2, 7, 3.5)
        path.cubicTo(12, -2, 17, 6, 7, 13)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E0245E"))
        painter.drawPath(path)


class Footer(QWidget):
    clicked = Signal()

    def __init__(self, with_grip: bool) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 6, 8, 10)
        lay.setSpacing(4)
        self.before = QLabel()
        self.after = QLabel()
        for label in (self.before, self.after):
            label.setObjectName("muted")
            label.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(self.before)
        lay.addWidget(HeartWidget())
        lay.addWidget(self.after)
        lay.addStretch(1)
        if with_grip:
            lay.addWidget(QSizeGrip(self))

    def retranslate(self) -> None:
        self.before.setText(t("footer.before"))
        self.after.setText(t("footer.after", lines=n(python_lines())))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
