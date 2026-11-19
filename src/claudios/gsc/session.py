"""Sitzung mit Google: Client, Token (nur im Arbeitsspeicher, optional im Anmeldeinformationsspeicher),
Property-Liste und die Prüfung für Stufe 2. Die Berechtigung wird vor JEDEM Scan live neu geprüft."""
from __future__ import annotations

import json
import time

import httpx

from ..core.errors import ClaudiosError, ErrorCode as E
from ..core.guard import normalize_input
from ..core.proof import issue, property_covers
from . import api, oauth
from .credstore import get_store

CLIENT_KEY = "Claudios/google-client"
REFRESH_KEY = "Claudios/google-refresh"
OK_LEVELS = ("siteOwner", "siteFullUser")


def match_property(sites: list[dict], host: str) -> str | None:
    """Property, die die GANZE Domain abdeckt und für die du Inhaber- oder Vollzugriff hast."""
    best: tuple[int, str] | None = None
    for entry in sites:
        site = str(entry.get("siteUrl", ""))
        if entry.get("permissionLevel") not in OK_LEVELS or not property_covers(site, host):
            continue
        rank = 0 if site.startswith("sc-domain:") else 1
        if best is None or rank < best[0]:
            best = (rank, site)
    return best[1] if best else None


class Session:
    def __init__(self, store=None) -> None:
        self.store = store if store is not None else get_store()
        self.client: oauth.Client | None = None
        self.refresh_token: str | None = None
        self.access: str | None = None
        self.expires = 0.0
        self.sites: list[dict] = []
        self.level2 = False
        self.use_data = True
        self.remember = False
        self.last_verified: tuple[str, str] | None = None
        self.csv_pages: list[dict] | None = None

    @property
    def signed_in(self) -> bool:
        return bool(self.access or self.refresh_token)

    def eligible_sites(self) -> list[dict]:
        return [s for s in self.sites if s.get("permissionLevel") in OK_LEVELS]

    def load_saved(self) -> None:
        try:
            raw = self.store.read(CLIENT_KEY)
            if raw:
                data = json.loads(raw)
                self.client = oauth.Client(data["id"], data["secret"])
            refresh = self.store.read(REFRESH_KEY)
            if refresh:
                self.refresh_token, self.remember = refresh, True
        except (ValueError, KeyError, TypeError, OSError, ClaudiosError):
            return

    def set_client(self, client: oauth.Client) -> None:
        self.client = client
        if self.store.persistent:
            self.store.write(CLIENT_KEY, json.dumps({"id": client.client_id, "secret": client.client_secret}))

    def set_tokens(self, tokens: oauth.Tokens, remember: bool) -> None:
        self.access, self.expires = tokens.access, tokens.expires_at
        if tokens.refresh:
            self.refresh_token = tokens.refresh
        self.remember = remember
        if remember and self.refresh_token and self.store.persistent:
            self.store.write(REFRESH_KEY, self.refresh_token)
        else:
            self.store.delete(REFRESH_KEY)

    def sign_out(self) -> None:
        self.access, self.refresh_token, self.expires = None, None, 0.0
        self.sites, self.level2, self.last_verified, self.remember = [], False, None, False
        self.store.delete(REFRESH_KEY)

    def access_token(self, http: httpx.Client | None = None) -> str:
        if self.access and time.time() < self.expires - 60:
            return self.access
        if self.client is None or not self.refresh_token:
            raise ClaudiosError(E.GOOGLE_AUTH, reason="not signed in")
        tokens = oauth.refresh_access(self.client, self.refresh_token, http)
        self.access, self.expires = tokens.access, tokens.expires_at
        return self.access

    def list_sites(self, http: httpx.Client | None = None) -> list[dict]:
        own = http is None
        client = http or api.new_client()
        try:
            self.sites = api.list_sites(client, self.access_token(client))
        finally:
            if own:
                client.close()
        return self.sites

    def verify(self, target, http: httpx.Client | None = None) -> str:
        sites = self.list_sites(http)
        prop = match_property(sites, target.host)
        if prop is None:
            raise ClaudiosError(E.GOOGLE_PROPERTY, host=target.host)
        self.last_verified = (target.host, prop)
        issue(target.host, prop)  # Beleg für genau diesen Scan: 15 Minuten, einmal
        return prop


SESSION = Session()


def scan_overrides(raw_url: str, allow_localhost: bool) -> dict:
    """Stufe-2-Angaben für den Scan, wenn Stufe 2 eingeschaltet ist. Prüft die Berechtigung live und wirft bei
    Fehlschlag einen Fehler mit Begründung (der Scan startet dann nicht)."""
    if not SESSION.level2:
        return {}
    try:
        target = normalize_input(raw_url, allow_localhost)
    except ClaudiosError:
        return {}  # den Eingabefehler meldet der Scan selbst
    if target.loopback:
        return {}
    return {"level": 2, "verified_property": SESSION.verify(target)}
