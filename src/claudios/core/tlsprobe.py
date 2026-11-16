"""Ein einziger TLS-Handshake zur geprüften öffentlichen IP: Restlaufzeit des Zertifikats und Protokollversion.
Es werden keine Anwendungsdaten gesendet. Alte Protokolle prüft später sslyze."""
from __future__ import annotations

import asyncio
import socket
import ssl
import time

from .errors import ClaudiosError
from .guard import resolve_public


def _handshake(host: str, ips: list[str]) -> dict:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    last: Exception | None = None
    for ip in ips[:3]:
        try:
            with socket.create_connection((ip, 443), timeout=10) as raw, \
                    ctx.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert() or {}
                version = tls.version() or ""
                cipher = tls.cipher()
        except OSError as exc:  # enthält ssl.SSLError
            last = exc
            continue
        expires = ssl.cert_time_to_seconds(cert["notAfter"])
        issuer = {key: value for part in cert.get("issuer", ()) for key, value in part}
        return {
            "version": version, "cipher": cipher[0] if cipher else "",
            "days_left": int((expires - time.time()) // 86400),
            "issuer": issuer.get("organizationName") or issuer.get("commonName", ""),
            "error": None,
        }
    return {"error": type(last).__name__ if last else "no address"}


async def probe_tls(resolver, snap) -> dict:
    host = snap.target.host
    try:
        ips = await resolve_public(resolver, host, False)
        return await asyncio.to_thread(_handshake, host, ips)
    except ClaudiosError as exc:
        return {"error": exc.code.value}
    except (KeyError, ValueError) as exc:
        return {"error": type(exc).__name__}