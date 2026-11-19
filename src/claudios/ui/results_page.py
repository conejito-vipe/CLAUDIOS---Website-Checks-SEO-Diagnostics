"""Ergebnisseite mit einer Korrektur: Ein abgebrochener Scan zeigt keine Gesamtwertung (sie wäre irreführend)."""
from __future__ import annotations

from ..core.numfmt import format_bytes
from ..core.redact import redact_url
from ..i18n.strings import get_lang, n, t
from .pages import ResultsPage as _ResultsPage


class ResultsPage(_ResultsPage):
    def refresh(self) -> None:
        super().refresh()
        result = self.result
        if result is None or result.snapshot.status != "aborted":
            return
        snap = result.snapshot
        self.summary.setText(t(
            "res.summary_aborted", target=redact_url(snap.target.url), status=t("status.aborted"),
            pages=n(len(snap.pages)), requests=n(result.requests),
            size=format_bytes(result.bytes_total, get_lang())))
