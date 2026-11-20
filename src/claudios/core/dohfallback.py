"""DNS über HTTPS (RFC 8484, POST) mit httpx, falls dnspython DoH selbst abgeschaltet meldet.

Im gebauten Programm war dns.query.have_doh False, obwohl httpx und httpcore importierbar sind. Dann ersetzt
install_if_needed() dns.query.https durch https_query. Verbindung wie in net.py: zur festen IP (bootstrap_address), SNI
und Zertifikatsprüfung gegen den Hostnamen, mindestens TLS 1.2, keine Umleitungen, keine Proxy-Umgebung, begrenzte
Antwortgröße. Ungeprüft gegen den echten Server unter Windows."""
from __future__ import annotations

import ssl
from urllib.parse import urlsplit, urlunsplit

import dns.exception
import dns.message
import dns.query
import httpx

MAX_BYTES = 65535


def https_query(q, where, timeout=None, bootstrap_address=None, *, _transport=None, **_ignored):
    parts = urlsplit(where)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("DoH needs an https:// address")
    url = where
    headers = {"content-type": "application/dns-message", "accept": "application/dns-message"}
    extensions: dict = {}
    if bootstrap_address:
        netloc = f"[{bootstrap_address}]" if ":" in bootstrap_address else bootstrap_address
        if parts.port:
            netloc += f":{parts.port}"
        url = urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))
        headers["host"] = parts.netloc
        extensions["sni_hostname"] = parts.hostname
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    with httpx.Client(verify=ctx, trust_env=False, follow_redirects=False, timeout=timeout or 5.0,
                      transport=_transport) as client:
        response = client.post(url, content=q.to_wire(), headers=headers, extensions=extensions)
    if response.status_code != 200:
        raise dns.exception.DNSException(f"DoH HTTP {response.status_code}")
    if len(response.content) > MAX_BYTES:
        raise dns.exception.DNSException("DoH response too large")
    return dns.message.from_wire(response.content)


def install_if_needed() -> str:
    """'native' (dnspython kann DoH selbst), 'fallback' (diese Datei springt ein) oder 'none'."""
    if getattr(dns.query, "have_doh", False):
        return "native"
    try:
        import httpcore  # noqa: F401
    except ImportError:
        return "none"
    dns.query.https = https_query
    return "fallback"
