"""Kleiner Client für feste Google-Dienste (Safe Browsing, PageSpeed). Bewusste Ausnahme vom Gatekeeper: Der Gatekeeper
kann nur GET und hat 15 Sekunden Zeitlimit. Hier gilt dafür: nur diese zwei festen Hosts, nur HTTPS auf Port 443,
keine Weiterleitung, keine Umgebungs-Proxys, Größenlimit, eigenes Zeitlimit. Die Namen löst das System auf, nicht DoH
(dieselbe Ausnahme wie bei der Google-Anmeldung). Adressen und Schlüssel erscheinen nie in Fehlermeldungen."""
from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlsplit

import httpx

from .. import USER_AGENT
from .errors import ClaudiosError, ErrorCode as E

ALLOWED_HOSTS = frozenset({"safebrowsing.googleapis.com", "www.googleapis.com"})


def _check(method: str, url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_HOSTS or parts.port not in (None, 443) \
            or parts.username or parts.password:
        raise ClaudiosError(E.INPUT_INVALID, reason="third-party host")
    if method not in ("GET", "POST"):
        raise ClaudiosError(E.INTERNAL, reason="method not allowed")
    return host


async def request(method: str, url: str, *, params: Sequence[tuple[str, str]] | dict | None = None,
                  json_body: dict | None = None, max_bytes: int, timeout: float, cancel=None,
                  transport=None) -> tuple[int, bytes, bool]:
    """(Status, Inhalt, abgeschnitten). Wirft ClaudiosError bei Verbindungs- oder Zeitfehlern."""
    host = _check(method, url)
    if cancel is not None and cancel.is_set():
        raise ClaudiosError(E.SCAN_CANCELLED)
    body, truncated = bytearray(), False
    try:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False, timeout=httpx.Timeout(timeout),
                                     headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                                     transport=transport) as client:
            async with client.stream(method, url, params=params, json=json_body) as resp:
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) >= max_bytes:
                        del body[max_bytes:]
                        truncated = True
                        break
                status = resp.status_code
    except httpx.TimeoutException:
        raise ClaudiosError(E.NET_TIMEOUT, url=host) from None
    except (httpx.HTTPError, OSError) as exc:
        raise ClaudiosError(E.NET_CONNECT, reason=type(exc).__name__) from None
    return status, bytes(body), truncated
