"""Eingabevalidierung, SSRF-Schutz, DoH-Auflösung. Eine Domain pro Scan, nur HTTPS, nur Port 443."""
from __future__ import annotations

import asyncio
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import dns.message
import dns.query
import dns.rdatatype
from publicsuffix2 import get_sld

from .errors import ClaudiosError, ErrorCode as E

DOH_URL = "https://dns.quad9.net/dns-query"
DOH_BOOTSTRAP = "9.9.9.9"


@dataclass(frozen=True)
class Target:
    url: str
    host: str
    registrable: str
    loopback: bool


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def ip_allowed(ip: str, allow_loopback: bool = False) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    if addr.is_loopback:
        return allow_loopback
    return addr.is_global and not addr.is_multicast


def normalize_input(raw: str, allow_localhost: bool = False) -> Target:
    s = (raw or "").strip()
    if not s:
        raise ClaudiosError(E.INPUT_EMPTY)
    if len(s) > 2048 or any(c.isspace() or ord(c) < 32 for c in s):
        raise ClaudiosError(E.INPUT_INVALID, reason="whitespace/length")
    if "://" not in s:
        s = "https://" + s
    try:
        p = urlsplit(s)
        port = p.port
    except ValueError:
        raise ClaudiosError(E.INPUT_INVALID, reason="parse") from None
    if p.username or p.password or "@" in p.netloc:
        raise ClaudiosError(E.INPUT_CREDENTIALS)
    host = (p.hostname or "").lower().rstrip(".")
    if not host or p.scheme not in ("http", "https"):
        raise ClaudiosError(E.INPUT_INVALID, reason="scheme/host")
    loop = is_loopback_host(host)
    if loop and not allow_localhost:
        raise ClaudiosError(E.TARGET_PRIVATE, host=host)
    if p.scheme == "http" and not loop:
        raise ClaudiosError(E.INPUT_NOT_HTTPS)
    if not loop:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise ClaudiosError(E.INPUT_INVALID, reason="idna") from None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ClaudiosError(E.INPUT_INVALID, reason="IP address")
        if port not in (None, 443):
            raise ClaudiosError(E.INPUT_INVALID, reason="port")
        if "." not in host:
            raise ClaudiosError(E.INPUT_INVALID, reason="no top-level domain")
    netloc = f"[{host}]" if ":" in host else host
    if port and (loop or port != 443):
        netloc += f":{port}"
    url = urlunsplit((p.scheme, netloc, p.path or "/", "", ""))
    return Target(url=url, host=host, registrable=host if loop else (get_sld(host) or host), loopback=loop)


class DohResolver:
    """DNS nur über HTTPS (DoH). Standard: Quad9."""

    def __init__(self, url: str = DOH_URL, bootstrap: str | None = DOH_BOOTSTRAP) -> None:
        if not url.startswith("https://"):
            raise ValueError("DoH resolver must use https://")
        self.url, self.bootstrap = url, bootstrap

    def _query(self, name: str, rtype: str) -> list[str]:
        q = dns.message.make_query(name, rtype, want_dnssec=False)
        r = dns.query.https(q, self.url, bootstrap_address=self.bootstrap, timeout=5)
        want = dns.rdatatype.from_text(rtype)
        return [rd.to_text() for rrset in r.answer if rrset.rdtype == want for rd in rrset]

    async def query(self, name: str, rtype: str) -> list[str]:
        return await asyncio.to_thread(self._query, name, rtype)

    async def addresses(self, host: str) -> list[str]:
        res = await asyncio.gather(self.query(host, "A"), self.query(host, "AAAA"), return_exceptions=True)
        ips = [ip for r in res if isinstance(r, list) for ip in r]
        if not ips:
            err = next((r for r in res if isinstance(r, Exception)), None)
            raise ClaudiosError(E.TARGET_NO_DNS, host=host, reason=type(err).__name__ if err else "no records")
        return ips


async def resolve_public(resolver: DohResolver, host: str, allow_loopback: bool) -> list[str]:
    """Löst auf und verlangt, dass ALLE Adressen öffentlich sind (Schutz gegen DNS-Tricks)."""
    if is_loopback_host(host):
        if not allow_loopback:
            raise ClaudiosError(E.TARGET_PRIVATE, host=host)
        return ["127.0.0.1"]
    ips = await resolver.addresses(host)
    if not all(ip_allowed(ip, allow_loopback) for ip in ips):
        raise ClaudiosError(E.TARGET_PRIVATE, host=host)
    return ips
