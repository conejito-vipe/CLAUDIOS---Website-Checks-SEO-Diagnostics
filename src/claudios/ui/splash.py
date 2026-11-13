"""Splash nach der Vorlage: Pill oben links, Logo mit Claim, dünner oranger Balken, Status und Prozent.
Die Schritte sind echt (keine Fake-Animation); der Balken ist nach Aufwand gewichtet."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..i18n.strings import n, t
from .widgets import CardWindow, load_logo


class Splash(CardWindow):
    ready = Signal()
    failed = Signal(object)

    def __init__(self, steps: list) -> None:
        super().__init__(with_lang=False)
        self.setFixedSize(940, 640)
        self._steps = steps
        self._index = 0
        self._done = 0
        self._total = sum(step[1] for step in steps)
        self._dismissed = False

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = load_logo()
        if pix is not None:
            logo.setPixmap(pix.scaledToHeight(340, Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("CLAUDIOS")
            logo.setObjectName("logofallback")
        self.body.addStretch(1)
        self.body.addWidget(logo)
        self.body.addStretch(1)

        bottom = QWidget()
        col = QVBoxLayout(bottom)
        col.setContentsMargins(24, 0, 24, 20)
        col.setSpacing(6)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        row = QHBoxLayout()
        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.percent = QLabel()
        self.percent.setObjectName("muted")
        row.addWidget(self.status, 1)
        row.addWidget(self.percent)
        col.addWidget(self.bar)
        col.addLayout(row)
        self.body.addWidget(bottom)
        self._show(0, "")

    def _pct(self) -> int:
        return int(self._done / self._total * 100) if self._total else 100

    def _show(self, pct: int, message: str) -> None:
        self.bar.setValue(pct)
        self.percent.setText(f"{n(pct)} %")
        self.status.setText(message)

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
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._dismissed:
            QApplication.quit()
        event.accept()
