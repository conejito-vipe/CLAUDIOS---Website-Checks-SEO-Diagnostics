from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .redact import redact_text, redact_url


class Severity(IntEnum):
    INFO = 0
    NOTE = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: Severity
    url: str
    msg_de: str
    msg_en: str
    evidence: str = ""

    def __post_init__(self) -> None:  # Sicherheitsnetz: nie Geheimnisse oder lange Belege speichern
        object.__setattr__(self, "evidence", redact_text(self.evidence)[:160])
        object.__setattr__(self, "url", redact_url(self.url))

    def msg(self, lang: str) -> str:
        return self.msg_de if lang == "de" else self.msg_en
