"""Snapshot: einmal crawlen, danach nur auswerten. Speichert KEINE Cookie-Werte."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup

from .guard import Target


@dataclass(frozen=True)
class CookieInfo:
    name: str
    secure: bool
    httponly: bool
    samesite: str | None
    lifetime_days: float | None
    path: str | None
    domain: str | None


def parse_set_cookie(line: str) -> CookieInfo:
    """Parst nur Name und Attribute, der Wert wird verworfen."""
    parts = [x.strip() for x in line.split(";")]
    name = parts[0].split("=", 1)[0].strip()[:100]
    attrs: dict[str, str] = {}
    for a in parts[1:]:
        k, _, v = a.partition("=")
        attrs[k.strip().lower()] = v.strip()
    life = None
    if "max-age" in attrs:
        try:
            life = float(attrs["max-age"]) / 86400
        except ValueError:
            pass
    elif "expires" in attrs:
        try:
            exp = parsedate_to_datetime(attrs["expires"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            life = (exp - datetime.now(UTC)).total_seconds() / 86400
        except (TypeError, ValueError):
            pass
    return CookieInfo(name, "secure" in attrs, "httponly" in attrs, attrs.get("samesite") or None,
                      life, attrs.get("path"), attrs.get("domain"))


@dataclass
class Page:
    url: str
    depth: int
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cookies: list[CookieInfo] = field(default_factory=list)
    html: str | None = None
    content_type: str = ""
    elapsed_ms: int = 0
    size: int = 0
    chain: list[str] = field(default_factory=list)
    blocked_redirect: str | None = None
    downgrade: bool = False
    truncated: bool = False
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    insecure_links: list[str] = field(default_factory=list)
    error: str | None = None
    _soup: Any = field(default=None, repr=False)

    @property
    def soup(self) -> BeautifulSoup | None:
        if self.html is None:
            return None
        if self._soup is None:
            self._soup = BeautifulSoup(self.html, "html.parser")
        return self._soup


@dataclass
class Snapshot:
    target: Target
    level: int
    profile: str
    started: float = field(default_factory=time.time)
    finished: float | None = None
    pages: list[Page] = field(default_factory=list)
    robots_txt: str | None = None
    skipped: list[dict] = field(default_factory=list)
    status: str = "running"            # complete | limited | aborted
    abort: dict | None = None
    extra: dict = field(default_factory=dict)

    def docs(self) -> list[Page]:
        return [p for p in self.pages if p.html is not None and p.status is not None]
