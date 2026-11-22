"""Splash nach der Vorlage: Pill oben links, Logo mit Claim, dünner oranger Balken, Status und Prozent. Die Schritte sind echt
(keine Fake-Animation); der Balken ist nach Aufwand gewichtet. Nach den Startschritten kann die Anwendung hier die
Einrichtung fehlender Komponenten anzeigen (show_progress, show_skip). Der Knopf „Später fortsetzen“ erscheint erst nach
SKIP_DELAY_MS. Zwischen Logo und Balken liegt ein fester Mindestabstand (LOGO_GAP)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..i18n.strings import n, t
from .widgets import CardWindow, load_logo

WIDTH, HEIGHT = 658, 448
LOGO_HEIGHT = 218
LOGO_GAP = 14
SKIP_DELAY_MS = 20000


class Splash(CardWindow):
    ready = Signal()
    failed = Signal(object)
    skipped = Signal()   # Nutzer will die Einrichtung später fortsetzen
    aborted = Signal()   # Fenster wurde geschlossen

    def __init__(self, steps: list) -> None:
        super().__init__(with_lang=False)
        self.setFixedSize(WIDTH, HEIGHT)
        self._steps = steps
        self._index = 0
        self._done = 0
        self._total = sum(step[1] for step in steps)
        self._dismissed = False

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = load_logo()
        if pix is not None:
            logo.setPixmap(pix.scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("CLAUDIOS")
            logo.setObjectName("logofallback")
        self.logo = logo
        self.body.addStretch(1)
        self.body.addWidget(logo)
        self.body.addStretch(1)
        self.body.addSpacing(LOGO_GAP)

        bottom = QWidget()
        self.bottom = bottom
        col = QVBoxLayout(bottom)
        col.setContentsMargins(24, 0, 24, 16)
        col.setSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        row = QHBoxLayout()
        row.setSpacing(16)
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(40)  # zwei Zeilen Platz, damit nichts überlappt
        self.status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.percent = QLabel()
        self.percent.setObjectName("muted")
        self.percent.setMinimumWidth(48)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.status, 1)
        row.addWidget(self.percent, 0, Qt.AlignmentFlag.AlignTop)
        self.skip_btn = QPushButton()
        self.skip_btn.setVisible(False)
        self.skip_btn.clicked.connect(lambda _checked=False: self.skipped.emit())
        self._skip_timer = QTimer(self)
        self._skip_timer.setSingleShot(True)
        self._skip_timer.timeout.connect(lambda: self.skip_btn.setVisible(True))
        col.addWidget(self.bar)
        col.addLayout(row)
        col.addWidget(self.skip_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.body.addWidget(bottom)
        self._show(0, "")

    def _pct(self) -> int:
        return int(self._done / self._total * 100) if self._total else 100

    def _show(self, pct: int, message: str) -> None:
        self.bar.setValue(pct)
        self.percent.setText(f"{n(pct)} %")
        self.status.setText(message)

    def show_progress(self, pct: int, message: str) -> None:
        self._show(pct, message)

    def show_skip(self, visible: bool, delay_ms: int = SKIP_DELAY_MS) -> None:
        """Zeigt „Später fortsetzen“ erst nach delay_ms (Standard 20 Sekunden)."""
        self.skip_btn.setText(t("boot.skip"))
        self._skip_timer.stop()
        if not visible:
            self.skip_btn.setVisible(False)
        elif delay_ms <= 0:
            self.skip_btn.setVisible(True)
        else:
            self.skip_btn.setVisible(False)
            self._skip_timer.start(delay_ms)

    def start(self) -> None:
        QTimer.singleShot(200, self._next)

    def _next(self) -> None:
        if self._index >= len(self._steps):
            self._show(100, t("splash.ready"))
            QTimer.singleShot(350, self.ready.emit)
            return
        key, weight, func = self._steps[self._index]
        self._show(self._pct(), t(key))
        QApplication.processEvents()
        try:
            func()
        except Exception as exc:  # Startfehler werden mit Grund angezeigt
            self.failed.emit(exc)
            return
        self._done += weight
        self._index += 1
        self._show(self._pct(), t(key))
        QTimer.singleShot(150, self._next)

    def dismiss(self) -> None:
        self._dismissed = True
        self._skip_timer.stop()
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._dismissed:
            self.aborted.emit()
            QApplication.quit()
        event.accept()
