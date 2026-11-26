"""Zentraler Netzwerk-Gatekeeper: JEDER Zugriff läuft hier durch (Guard, Rate-Limit, IP-Pinning, Limits)."""
from __future__ import annotations

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from publicsuffix2 import get_sld

from .. import USER_AGENT
from .errors import ClaudiosError, ErrorCode as E
from .guard import DohResolver, Target, is_loopback_host, resolve_public
from .limits import LIMITS
from .redact import redact_text, redact_url
from .snapshot import CookieInfo, parse_set_cookie

log = logging.getLogger("claudios.net")
REDIRECTS = {301, 302, 303, 307, 308}
DROP_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
EXTRA_HEADERS = {"sec-gpc"}  # nur dieses eine zusätzliche Anfrage-Signal ist erlaubt (Global Privacy Control)


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    cookies: list[CookieInfo]
    body: bytes
    truncated: bool
    elapsed_ms: int
    chain: list[str] = field(default_factory=list)
    blocked_redirect: str | None = None
    downgrade: bool = False

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())


def _causes(exc: BaseException):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


class Gatekeeper:
    def __init__(self, target: Target, *, resolver: DohResolver, allow_localhost: bool = False,
                 cancel: asyncio.Event | None = None) -> None:
        self.target, self.resolver, self.allow_localhost, self.cancel = target, resolver, allow_localhost, cancel
        self.requests = 0
        self.bytes_total = 0
        self._interval = 1.0 / min(LIMITS.requests_per_second, LIMITS.requests_per_second_max)
        self._next = 0.0
        self._pace_lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(LIMITS.connections_per_host)
        self._ips: dict[str, list[str]] = {}
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self._client = httpx.AsyncClient(
            verify=ctx, follow_redirects=False, trust_env=False,
            timeout=httpx.Timeout(LIMITS.request_timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.5"},
            limits=httpx.Limits(max_connections=LIMITS.connections_per_host,
                                max_keepalive_connections=LIMITS.connections_per_host),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def same_site(self, host: str) -> bool:
        if host == self.target.host:
            return True
        return not self.target.loopback and (get_sld(host) or host) == self.target.registrable

    def _check_cancel(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise ClaudiosError(E.SCAN_CANCELLED)

    async def _pace(self) -> None:
        async with self._pace_lock:
            now = time.monotonic()
            wait = self._next - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next = max(now, self._next) + self._interval

    async def _validate(self, url: str, external: bool, plain: bool = False) -> list[str]:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        loop = is_loopback_host(host)
        if p.username or p.password:
            raise ClaudiosError(E.INPUT_CREDENTIALS)
        if p.scheme != "https" and not (plain and p.scheme == "http") \
                and not (loop and self.allow_localhost and p.scheme == "http"):
            raise ClaudiosError(E.NET_DOWNGRADE, url=redact_url(url))
        if not loop and p.port not in (None, 443):
            raise ClaudiosError(E.INPUT_INVALID, reason="port")
        if not external and not self.same_site(host):
            raise ClaudiosError(E.NET_CROSS_SITE, host=host)
        if host not in self._ips:  # einmal auflösen, prüfen und die geprüfte IP für die Verbindung festhalten
            self._ips[host] = await resolve_public(self.resolver, host, self.allow_localhost)
        return self._ips[host]

    def _map(self, exc: Exception, url: str) -> ClaudiosError:
        if isinstance(exc, ClaudiosError):
            return exc
        host = urlsplit(url).hostname or ""
        chain = list(_causes(exc))
        for e in chain:
            if isinstance(e, ssl.SSLCertVerificationError):
                return ClaudiosError(E.TLS_CERT, host=host, reason=e.verify_message or str(e))
        for e in chain:
            if isinstance(e, ssl.SSLError):
                return ClaudiosError(E.TLS_HANDSHAKE, reason=str(e))
        if isinstance(exc, httpx.TimeoutException):
            return ClaudiosError(E.NET_TIMEOUT, url=redact_url(url))
        if isinstance(exc, (httpx.HTTPError, OSError)):
            return ClaudiosError(E.NET_CONNECT, reason=type(exc).__name__)
        log.error("unexpected network error: %r", exc)
        return ClaudiosError(E.INTERNAL, reason=type(exc).__name__)

    async def _once(self, url: str, method: str, ips: list[str], max_bytes: int | None,
                    extra: dict[str, str] | None = None) -> Response:
        p = urlsplit(url)
        host = p.hostname or ""
        req_url, headers, ext = url, dict(extra or {}), {}
        if not is_loopback_host(host):  # IP-Pinning: zur geprüften IP verbinden, Zertifikat gegen den Hostnamen prüfen
            ip = ips[0]
            netloc = (f"[{ip}]" if ":" in ip else ip) + (f":{p.port}" if p.port else "")
            req_url = urlunsplit((p.scheme, netloc, p.path or "/", p.query, ""))
            headers["Host"] = p.netloc
            ext["sni_hostname"] = host
        cap = min(max_bytes or LIMITS.max_response_bytes, LIMITS.max_response_bytes)
        await self._pace()
        async with self._sem:
            t0 = time.monotonic()
            try:
                async with self._client.stream(method, req_url, headers=headers, extensions=ext) as r:
                    body, truncated = bytearray(), False
                    if method != "HEAD":
                        async for chunk in r.aiter_bytes():
                            body += chunk
                            if len(body) >= cap:
                                del body[cap:]
                                truncated = True
                                break
                    hdrs: dict[str, str] = {}
                    for k, v in r.headers.multi_items():
                        k = k.lower()
                        if k not in DROP_HEADERS:
                            v = redact_text(v)
                            hdrs[k] = f"{hdrs[k]}, {v}" if k in hdrs else v
                    cookies = [parse_set_cookie(c) for c in r.headers.get_list("set-cookie")]
                    status = r.status_code
            except Exception as exc:  # noqa: BLE001 – wird zentral in ClaudiosError übersetzt
                raise self._map(exc, url) from None
        self._client.cookies.clear()  # keine Sitzung über Anfragen hinweg
        self.requests += 1
        self.bytes_total += len(body)
        if self.bytes_total > LIMITS.max_scan_bytes:
            raise ClaudiosError(E.LIMIT_BYTES, limit=f"{LIMITS.max_scan_bytes // (1024 * 1024)} MB")
        return Response(url, status, hdrs, cookies, bytes(body), truncated, int((time.monotonic() - t0) * 1000))

    async def fetch(self, url: str, *, method: str = "GET", follow: bool = True,
                    max_bytes: int | None = None, external: bool = False, plain: bool = False,
                    headers: dict[str, str] | None = None) -> Response:
        """plain=True erlaubt EINE unverschlüsselte Anfrage ohne Weiterleitung (Test der http-Variante der eigenen
        Domain). headers: nur Signale aus EXTRA_HEADERS."""
        if method not in ("GET", "HEAD"):
            raise ClaudiosError(E.INTERNAL, reason="method not allowed")
        if plain and (follow or external):
            raise ClaudiosError(E.INTERNAL, reason="plain needs follow=False and no external host")
        extra = {k: str(v) for k, v in (headers or {}).items()}
        if any(k.lower() not in EXTRA_HEADERS for k in extra):
            raise ClaudiosError(E.INTERNAL, reason="header not allowed")
        chain: list[str] = []
        cur = url
        while True:
            self._check_cancel()
            ips = await self._validate(cur, external, plain)
            resp = await self._once(cur, method, ips, max_bytes, extra)
            resp.chain = list(chain)
            loc = resp.header("location")
            if not (follow and resp.status in REDIRECTS and loc):
                return resp
            nxt = urljoin(cur, loc).split("#")[0]
            chain.append(cur)
            if len(chain) > LIMITS.max_redirects or nxt in chain or nxt == cur:
                raise ClaudiosError(E.NET_REDIRECTS, url=redact_url(url))
            n = urlsplit(nxt)
            nhost = (n.hostname or "").lower()
            secure_ok = n.scheme == "https" or (is_loopback_host(nhost) and self.allow_localhost and n.scheme == "http")
            if not secure_ok:
                resp.blocked_redirect, resp.downgrade = nxt, True
                return resp
            if not external and not self.same_site(nhost):
                resp.blocked_redirect = nxt
                return resp
            cur = nxt
