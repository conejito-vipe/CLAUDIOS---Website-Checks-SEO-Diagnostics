"""Gemeinsame Bausteine: rahmenloses Fenster mit Schatten, Titelleiste, Footer mit gezeichnetem Herz. Die Fenstergröße
ändert man am Rand (die äußeren Pixel der Karte); ein festgelegter Größenbereich (Splash) schaltet das ab."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..buildinfo import python_lines
from ..i18n.strings import n, t
from ..paths import assets_dir

MARGIN = 14  # Schattenrand um die Karte
EDGE = 8     # Breite der Zone am Kartenrand, in der die Größe geändert wird


def load_logo() -> QPixmap | None:
    folder = assets_dir()
    if folder is not None:
        path = folder / "logo-full.png"
        if path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                return pix
    return None


def trimmed(pix: QPixmap, threshold: int = 24) -> QPixmap:
    """Schneidet den leeren (durchsichtigen) Rand ab, damit das Logo in jeder Größe den Platz ausfüllt."""
    image = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    left, top, right, bottom = image.width(), image.height(), -1, -1
    for y in range(image.height()):
        for x in range(image.width()):
            if (image.pixel(x, y) >> 24) > threshold:
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    if right < left:
        return pix
    return pix.copy(left, top, right - left + 1, bottom - top + 1)


def load_icon() -> QIcon | None:
    folder = assets_dir()
    if folder is not None:
        for name in ("logo-icon.png", "logo-full.png"):
            path = folder / name
            if path.is_file():
                return QIcon(str(path))
    return None


FLAG_SIZE = (24, 16)
LANG_NAMES = {"de": "Deutsch", "en": "English (US)"}


def flag_icon(code: str) -> QIcon:
    """Gezeichnete Flagge (de: Deutschland, sonst USA): Emoji-Flaggen zeigt Windows meist als Buchstaben."""
    w, h = FLAG_SIZE
    scale = 2
    pix = QPixmap(w * scale, h * scale)
    pix.setDevicePixelRatio(scale)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = QPainterPath()
    outline.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 2.5, 2.5)
    painter.setClipPath(outline)
    painter.setPen(Qt.PenStyle.NoPen)
    if code == "de":
        for index, color in enumerate(("#000000", "#DD0000", "#FFCE00")):
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(0, index * h / 3, w, h / 3 + 0.5))
    else:
        stripe = h / 13
        for index in range(13):
            painter.setBrush(QColor("#B22234" if index % 2 == 0 else "#FFFFFF"))
            painter.drawRect(QRectF(0, index * stripe, w, stripe + 0.4))
        painter.setBrush(QColor("#3C3B6E"))
        painter.drawRect(QRectF(0, 0, w * 0.42, stripe * 7))
        painter.setBrush(QColor("#FFFFFF"))
        for row in range(3):
            for col in range(4):
                painter.drawEllipse(QPointF(1.5 + col * 2.4, 1.5 + row * 2.4), 0.55, 0.55)
    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QColor(0, 0, 0, 70))
    painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 2.5, 2.5)
    painter.end()
    return QIcon(pix)


def cursor_for(edges) -> Qt.CursorShape:
    left, right = bool(edges & Qt.Edge.LeftEdge), bool(edges & Qt.Edge.RightEdge)
    top, bottom = bool(edges & Qt.Edge.TopEdge), bool(edges & Qt.Edge.BottomEdge)
    if (left or right) and (top or bottom):
        return Qt.CursorShape.SizeFDiagCursor if (left and top) or (right and bottom) else Qt.CursorShape.SizeBDiagCursor
    return Qt.CursorShape.SizeHorCursor if (left or right) else Qt.CursorShape.SizeVerCursor


class TitleBar(QWidget):
    langChanged = Signal(str)
    helpRequested = Signal()

    def __init__(self, with_lang: bool) -> None:
        super().__init__()
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 12, 0)
        self.pill = QLabel("CLAUDIOS")
        self.pill.setObjectName("pill")
        self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Schriftzug in der Mitte des Chips
        lay.addWidget(self.pill)
        lay.addStretch(1)
        self._lang_buttons: dict[str, QPushButton] = {}
        self.btn_help = QPushButton(t("nav.help"))
        self.btn_help.setObjectName("langbtn")
        self.btn_help.clicked.connect(lambda _checked=False: self.helpRequested.emit())
        self.btn_help.setVisible(with_lang)
        lay.addWidget(self.btn_help)
        if with_lang:
            group = QButtonGroup(self)
            group.setExclusive(True)
            for code in ("de", "en"):
                btn = QPushButton()
                btn.setObjectName("langbtn")
                btn.setIcon(flag_icon(code))
                btn.setIconSize(QSize(*FLAG_SIZE))
                btn.setToolTip(LANG_NAMES[code])
                btn.setAccessibleName(LANG_NAMES[code])
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
        self.btn_min.setProperty("role", "min")
        self.btn_close.setProperty("role", "close")
        self.btn_min.clicked.connect(self._minimize)
        self.btn_close.clicked.connect(self._close)

    def _minimize(self) -> None:
        self.window().showMinimized()

    def _close(self) -> None:
        self.window().close()

    def set_help_text(self, text: str) -> None:
        self.btn_help.setText(text)

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
        self._centered = False
        self._filtering = False
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
        self.titlebar = TitleBar(with_lang)
        self.body.addWidget(self.titlebar)

    def resizable(self) -> bool:
        return self.minimumSize() != self.maximumSize()

    def _edges_at(self, pos):
        """Welche Fensterkanten liegen an dieser Position (leer, wenn nicht am Rand oder nicht skalierbar)?"""
        edges = Qt.Edge(0)
        if not self.resizable():
            return edges
        if pos.x() <= MARGIN + EDGE:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= self.width() - MARGIN - EDGE:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= MARGIN + EDGE:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= self.height() - MARGIN - EDGE:
            edges |= Qt.Edge.BottomEdge
        return edges

    def center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            self.center_on_screen()
        app = QApplication.instance()
        if app is not None and self.resizable() and not self._filtering:
            app.installEventFilter(self)
            self._filtering = True

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        app = QApplication.instance()
        if app is not None and self._filtering:
            app.removeEventFilter(self)
            self._filtering = False
        super().closeEvent(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt-Name)
        kind = event.type()
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove) and isinstance(watched, QWidget) \
                and watched.window() is self:
            edges = self._edges_at(self.mapFromGlobal(event.globalPosition().toPoint()))
            if kind == QEvent.Type.MouseMove and event.buttons() == Qt.MouseButton.NoButton:
                if edges:
                    self.setCursor(cursor_for(edges))
                else:
                    self.unsetCursor()
            elif kind == QEvent.Type.MouseButtonPress and edges and event.button() == Qt.MouseButton.LeftButton:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    return True
        return super().eventFilter(watched, event)


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
    """Fußzeile, im Fenster zentriert. with_grip bleibt aus Kompatibilitätsgründen, die Größe ändert man am Rand."""

    clicked = Signal()

    def __init__(self, with_grip: bool = False) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 6, 20, 12)
        lay.setSpacing(4)
        self.before = QLabel()
        self.after = QLabel()
        for label in (self.before, self.after):
            label.setObjectName("muted")
            label.setTextFormat(Qt.TextFormat.PlainText)
        lay.addStretch(1)
        lay.addWidget(self.before)
        lay.addWidget(HeartWidget())
        lay.addWidget(self.after)
        lay.addStretch(1)

    def retranslate(self) -> None:
        self.before.setText(t("footer.before"))
        self.after.setText(t("footer.after", lines=n(python_lines())))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
