"""Anmeldung bei Google per OAuth 2.0 für Desktop-Programme (PKCE, State, einmaliger Rückgabeport auf 127.0.0.1).
Dein Google-Passwort sieht Claudios nie: die Anmeldung läuft im Browser. Angefordert wird nur der Lesezugriff auf die
Search Console. Die Rückgabeadresse auf dem eigenen Rechner ist unverschlüsselt (Loopback). Google schreibt das für
Desktop-Programme so vor. Sie ist die dokumentierte Ausnahme der Nur-HTTPS-Regel."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from ..core.errors import ClaudiosError, ErrorCode as E

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
HOST = "127.0.0.1"
SCHEME = "http"
WAIT_SECONDS = 180.0
_PAGE = (b"<!doctype html><meta charset=utf-8><title>Claudios</title>"
         b"<p>Claudios: Anmeldung abgeschlossen / sign-in finished. Du kannst dieses Fenster schliessen / "
         b"You can close this window.</p>")


@dataclass(frozen=True)
class Client:
    client_id: str
    client_secret: str = field(repr=False)


@dataclass(frozen=True)
class Tokens:
    access: str = field(repr=False)
    refresh: str | None = field(default=None, repr=False)
    expires_at: float = 0.0


def parse_client_json(text: str) -> Client:
    """Liest die von Google heruntergeladene client_secret.json (nur Typ 'Desktop')."""
    try:
        data = json.loads(text)
    except ValueError:
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="not JSON") from None
    section = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="not a client of type Desktop")
    client_id, secret = section.get("client_id"), section.get("client_secret")
    if not (isinstance(client_id, str) and client_id and isinstance(secret, str) and secret):
        raise ClaudiosError(E.GOOGLE_IMPORT, reason="client_id or client_secret missing")
    return Client(client_id, secret)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def auth_url(client: Client, redirect_uri: str, challenge: str, state: str) -> str:
    query = urlencode({
        "client_id": client.client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
        "access_type": "offline", "prompt": "consent"})
    return f"{AUTH_URL}?{query}"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (Name von der Basisklasse)
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        server = self.server
        if parts.path != "/" or not ({"code", "error"} & set(query)):
            self.send_response(404)
            self.end_headers()
            return
        if query.get("state", [""])[0] != server.expected_state:
            server.result = {"error": "state mismatch"}
        elif "error" in query:
            server.result = {"error": query["error"][0][:40]}
        else:
            server.result = {"code": query["code"][0]}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_PAGE)))
        self.end_headers()
        self.wfile.write(_PAGE)

    def log_message(self, *args) -> None:  # kein Protokoll: die Adresse enthält den Code
        return None


def _wait(server: HTTPServer, wait: float, cancel: threading.Event | None) -> dict:
    deadline = time.monotonic() + wait
    server.timeout = 0.3
    while server.result is None:
        if cancel is not None and cancel.is_set():
            raise ClaudiosError(E.GOOGLE_AUTH, reason="cancelled")
        if time.monotonic() >= deadline:
            raise ClaudiosError(E.GOOGLE_AUTH, reason="timeout")
        server.handle_request()
    return server.result


def _post(http: httpx.Client, data: dict) -> Tokens:
    try:
        resp = http.post(TOKEN_URL, data=data)
    except httpx.HTTPError as exc:
        raise ClaudiosError(E.GOOGLE_AUTH, reason=type(exc).__name__) from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200 or not isinstance(body, dict) or "access_token" not in body:
        reason = body.get("error") if isinstance(body, dict) else None
        raise ClaudiosError(E.GOOGLE_AUTH, reason=str(reason or f"HTTP {resp.status_code}")[:60])
    return Tokens(access=body["access_token"], refresh=body.get("refresh_token"),
                  expires_at=time.time() + int(body.get("expires_in", 3600)))


def _with_http(http: httpx.Client | None, data: dict) -> Tokens:
    if http is not None:
        return _post(http, data)
    with httpx.Client(timeout=20.0, trust_env=False) as own:
        return _post(own, data)


def exchange_code(client: Client, code: str, verifier: str, redirect_uri: str,
                  http: httpx.Client | None = None) -> Tokens:
    return _with_http(http, {
        "grant_type": "authorization_code", "code": code, "code_verifier": verifier, "redirect_uri": redirect_uri,
        "client_id": client.client_id, "client_secret": client.client_secret})


def refresh_access(client: Client, refresh_token: str, http: httpx.Client | None = None) -> Tokens:
    return _with_http(http, {
        "grant_type": "refresh_token", "refresh_token": refresh_token,
        "client_id": client.client_id, "client_secret": client.client_secret})


def sign_in(client: Client, open_browser, *, http: httpx.Client | None = None, wait: float = WAIT_SECONDS,
            cancel: threading.Event | None = None) -> Tokens:
    """Öffnet die Google-Anmeldung im Browser und wartet einmalig auf die Rückkehr auf 127.0.0.1."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(24)
    server = HTTPServer((HOST, 0), _Handler)
    server.expected_state, server.result = state, None
    try:
        redirect = f"{SCHEME}://{HOST}:{server.server_address[1]}"
        open_browser(auth_url(client, redirect, challenge, state))
        result = _wait(server, wait, cancel)
    finally:
        server.server_close()
    if "error" in result:
        raise ClaudiosError(E.GOOGLE_AUTH, reason=result["error"])
    return exchange_code(client, result["code"], verifier, redirect, http)
