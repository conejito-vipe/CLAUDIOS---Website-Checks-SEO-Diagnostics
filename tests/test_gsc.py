import asyncio
import base64
import hashlib
import json
import secrets
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from claudios.core import probe_gsc
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.snapshot import Page, Snapshot
from claudios.gsc import api, credstore, csvimport, oauth, session
from claudios.gsc.credstore import MemoryStore
from claudios.gsc.session import Session, match_property, scan_overrides
from claudios.i18n.strings import TEXTS

CLIENT = oauth.Client("id.apps.test", "S3CR3T-CLIENT-VALUE")
SITES = [
    {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"},
    {"siteUrl": "https://www.other.test/", "permissionLevel": "siteFullUser"},
    {"siteUrl": "https://example.org/", "permissionLevel": "siteRestrictedUser"},
    {"siteUrl": "https://sub.third.test/blog/", "permissionLevel": "siteOwner"},
    {"siteUrl": "http" + "://plain.test/", "permissionLevel": "siteOwner"},
]


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


# ------------------------------------------------------------------ Anmeldung

def test_pkce_and_authorization_url():
    verifier, challenge = oauth.pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    url = oauth.auth_url(CLIENT, "http" + "://127.0.0.1:5555", challenge, "STATE1")
    parts, query = urlsplit(url), parse_qs(urlsplit(url).query)
    assert parts.scheme == "https" and parts.hostname == "accounts.google.com"
    assert query["scope"] == [oauth.SCOPE] and oauth.SCOPE.endswith("webmasters.readonly")
    assert query["code_challenge_method"] == ["S256"] and query["state"] == ["STATE1"]
    assert query["response_type"] == ["code"] and "S3CR3T" not in url


def token_client(calls, status=200, body=None):
    def handler(request):
        calls.append(parse_qs(request.content.decode()))
        payload = body or {"access_token": "ACCESS-TOKEN-VALUE", "refresh_token": "REFRESH-TOKEN-VALUE",
                           "expires_in": 3600}
        return httpx.Response(status, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))


def fake_browser(result_query):
    def open_browser(url):
        query = parse_qs(urlsplit(url).query)
        redirect, state = query["redirect_uri"][0], query["state"][0]

        def go():
            with httpx.Client(trust_env=False, timeout=5) as client:
                client.get(redirect + "/favicon.ico")
                client.get(redirect + "/?" + result_query.format(state=state))

        threading.Thread(target=go, daemon=True).start()
    return open_browser


def test_sign_in_exchanges_the_code_with_pkce_and_hides_tokens():
    calls: list = []
    tokens = oauth.sign_in(CLIENT, fake_browser("code=THECODE&state={state}"), http=token_client(calls), wait=10)
    assert tokens.access == "ACCESS-TOKEN-VALUE" and tokens.refresh == "REFRESH-TOKEN-VALUE"
    assert tokens.expires_at > time.time()
    form = calls[0]
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["THECODE"]
    assert len(form["code_verifier"][0]) >= 43 and form["client_secret"] == [CLIENT.client_secret]
    assert form["redirect_uri"][0].startswith("http" + "://127.0.0.1:")
    assert "TOKEN-VALUE" not in repr(tokens) and "S3CR3T" not in repr(CLIENT)


@pytest.mark.parametrize("query", ["code=X&state=WRONG", "error=access_denied&state={state}"])
def test_sign_in_rejects_a_wrong_state_and_a_denial(query):
    calls: list = []
    with pytest.raises(ClaudiosError) as e:
        oauth.sign_in(CLIENT, fake_browser(query), http=token_client(calls), wait=10)
    assert e.value.code == E.GOOGLE_AUTH and calls == []


def test_sign_in_times_out_can_be_cancelled_and_reports_token_errors():
    with pytest.raises(ClaudiosError) as e:
        oauth.sign_in(CLIENT, lambda url: None, http=token_client([]), wait=0.4)
    assert e.value.code == E.GOOGLE_AUTH and e.value.ctx["reason"] == "timeout"
    stop = threading.Event()
    stop.set()
    with pytest.raises(ClaudiosError) as e:
        oauth.sign_in(CLIENT, lambda url: None, http=token_client([]), wait=30, cancel=stop)
    assert e.value.ctx["reason"] == "cancelled"
    with pytest.raises(ClaudiosError) as e:
        oauth.refresh_access(CLIENT, "R", token_client([], status=400, body={"error": "invalid_grant"}))
    assert e.value.ctx["reason"] == "invalid_grant"


def test_client_file_must_be_a_desktop_client():
    good = json.dumps({"installed": {"client_id": "a.apps.test", "client_secret": "s"}})
    assert oauth.parse_client_json(good).client_id == "a.apps.test"
    for bad in ("not json", json.dumps({"web": {"client_id": "a", "client_secret": "s"}}),
                json.dumps({"installed": {"client_id": "a"}}), "[]"):
        with pytest.raises(ClaudiosError) as e:
            oauth.parse_client_json(bad)
        assert e.value.code == E.GOOGLE_IMPORT


# ------------------------------------------------------------------ Property und Sitzung

@pytest.mark.parametrize("host,expected", [
    ("example.com", "sc-domain:example.com"), ("shop.example.com", "sc-domain:example.com"),
    ("notexample.com", None), ("www.other.test", "https://www.other.test/"), ("other.test", None),
    ("example.org", None), ("sub.third.test", None), ("plain.test", None)])
def test_property_must_cover_the_whole_domain_with_enough_rights(host, expected):
    assert match_property(SITES, host) == expected


class Google:
    def __init__(self, sites=None, rows=None, sitemaps=None, inspect=None, status=200):
        self.sites, self.rows, self.sitemaps = sites or [], rows or [], sitemaps or []
        self.inspect, self.status, self.calls, self.bodies = inspect or {}, status, [], []

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request):
        url = str(request.url)
        self.calls.append((request.method, url, request.headers.get("authorization")))
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ACCESS-TOKEN-VALUE", "expires_in": 3600})
        if self.status != 200:
            return httpx.Response(self.status, json={})
        if "index:inspect" in url:
            body = json.loads(request.content)
            self.bodies.append(body)
            result = self.inspect.get(body["inspectionUrl"], {})
            return httpx.Response(200, json={"inspectionResult": {"indexStatusResult": result}})
        if "searchAnalytics/query" in url:
            self.bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"rows": self.rows})
        if url.endswith("/sitemaps"):
            return httpx.Response(200, json={"sitemap": self.sitemaps})
        if url.endswith("/webmasters/v3/sites"):
            return httpx.Response(200, json={"siteEntry": self.sites})
        return httpx.Response(404, json={})


def make_session(store=None):
    state = Session(store or MemoryStore(persistent=True))
    state.client, state.access, state.expires = CLIENT, "ACCESS-TOKEN-VALUE", time.time() + 3600
    return state


def test_tokens_stay_in_memory_unless_the_user_asks_otherwise():
    store = MemoryStore(persistent=True)
    state = Session(store)
    state.set_tokens(oauth.Tokens("A", "R", time.time() + 3600), remember=False)
    assert store.data == {} and state.signed_in
    state.set_tokens(oauth.Tokens("A", "R", time.time() + 3600), remember=True)
    assert store.data == {session.REFRESH_KEY: "R"}
    state.level2 = True
    state.sign_out()
    assert store.data == {} and not state.signed_in and not state.level2
    never = Session(MemoryStore(persistent=False))
    never.set_tokens(oauth.Tokens("A", "R", time.time() + 3600), remember=True)
    assert never.store.data == {}


def test_expired_tokens_are_refreshed_and_the_client_can_be_remembered():
    store = MemoryStore(persistent=True)
    state = Session(store)
    state.set_client(CLIENT)
    fresh = Session(store)
    fresh.load_saved()
    assert fresh.client == CLIENT
    fresh.access, fresh.expires, fresh.refresh_token = "old", time.time() - 10, "R"
    calls: list = []
    assert fresh.access_token(token_client(calls)) == "ACCESS-TOKEN-VALUE"
    assert calls[0]["grant_type"] == ["refresh_token"]
    with pytest.raises(ClaudiosError) as e:
        Session(MemoryStore()).access_token()
    assert e.value.code == E.GOOGLE_AUTH


def test_verification_is_checked_live_against_the_property_list():
    google = Google(sites=SITES)
    state = make_session()
    assert state.verify(normalize_input("shop.example.com"), google.client()) == "sc-domain:example.com"
    assert state.last_verified == ("shop.example.com", "sc-domain:example.com")
    assert google.calls[0][2] == "Bearer ACCESS-TOKEN-VALUE"
    with pytest.raises(ClaudiosError) as e:
        state.verify(normalize_input("example.org"), google.client())
    assert e.value.code == E.GOOGLE_PROPERTY


def test_scan_overrides_need_level_2_to_be_switched_on(monkeypatch):
    state = make_session()
    monkeypatch.setattr(session, "SESSION", state)
    assert scan_overrides("example.com", False) == {}
    state.level2 = True
    monkeypatch.setattr(state, "verify", lambda target, http=None: "sc-domain:example.com")
    assert scan_overrides("example.com", False) == {"level": 2, "verified_property": "sc-domain:example.com"}
    assert scan_overrides("", False) == {} and scan_overrides("localhost:8000", True) == {}

    def deny(target, http=None):
        raise ClaudiosError(E.GOOGLE_PROPERTY, host="example.com")

    monkeypatch.setattr(state, "verify", deny)
    with pytest.raises(ClaudiosError) as e:
        scan_overrides("example.com", False)
    assert e.value.code == E.GOOGLE_PROPERTY


@pytest.fixture
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_scan_worker_applies_the_level_2_overrides(qapp, monkeypatch):
    from claudios.ui import worker

    seen: dict = {}

    async def fake_run_scan(**kwargs):
        seen.update(kwargs)
        return "result"

    monkeypatch.setattr(worker, "run_scan", fake_run_scan)
    monkeypatch.setattr(worker, "scan_overrides", lambda raw, local: {"level": 2, "verified_property": "P"})
    thread = worker.ScanThread({"raw_url": "example.com", "level": 1, "profile": "standard", "confirmed": True})
    assert asyncio.run(thread._main()) == "result"
    assert seen["level"] == 2 and seen["verified_property"] == "P" and seen["confirmed"] is True


# ------------------------------------------------------------------ Schnittstelle und CSV

def test_api_functions_parse_the_answers_and_never_ask_for_search_terms():
    google = Google(sites=SITES, rows=[{"keys": ["https://example.com/"], "clicks": 5.0, "impressions": 100.0}, {}],
                    sitemaps=[{"path": "https://example.com/s.xml?token=abc", "errors": "2", "warnings": "1"}],
                    inspect={"https://example.com/": {"verdict": "PASS", "coverageState": "Indexed"}})
    http = google.client()
    assert len(api.list_sites(http, "T")) == 5
    rows, truncated = api.top_pages(http, "T", "sc-domain:example.com")
    assert rows == [{"url": "https://example.com/", "clicks": 5, "impressions": 100}] and truncated is False
    sitemap = api.sitemaps(http, "T", "sc-domain:example.com")[0]
    assert sitemap["errors"] == 2 and sitemap["warnings"] == 1 and "abc" not in sitemap["path"]
    assert api.inspect(http, "T", "sc-domain:example.com", "https://example.com/")["verdict"] == "PASS"
    assert [b["dimensions"] for b in google.bodies if "dimensions" in b] == [["page"]]
    with pytest.raises(ClaudiosError) as e:
        api.list_sites(Google(status=401).client(), "T")
    assert e.value.code == E.GOOGLE_AUTH


def test_csv_import_reads_english_and_german_exports_and_rejects_other_files():
    english = 'Top pages,Clicks,Impressions,CTR,Position\nhttps://example.com/,5,"1,200",2.1%,3.2\nbad,1,1,1,1\n'
    rows = csvimport.parse_pages_csv(english.encode())
    assert rows == [{"url": "https://example.com/", "impressions": 1200, "clicks": 5}]
    german = "\ufeffHäufigste Seiten;Klicks;Impressionen;CTR;Position\nhttps://example.com/a;5;1.200;2,1 %;3,2\n"
    assert csvimport.parse_pages_csv(german.encode("utf-8"))[0]["impressions"] == 1200
    for bad in ("", "Top queries,Clicks\nshoes,1\n", "Top queries,Clicks,Impressions\nbuy shoes,1,2\n"):
        with pytest.raises(ClaudiosError) as e:
            csvimport.parse_pages_csv(bad.encode())
        assert e.value.code == E.GOOGLE_IMPORT
    with pytest.raises(ClaudiosError):
        csvimport.parse_pages_csv(b"x" * (csvimport.MAX_BYTES + 1))


# ------------------------------------------------------------------ Probe und Prüfungen

def make_snap(level=2):
    snap = Snapshot(target=normalize_input("example.com"), level=level, profile="standard")
    for url, status in (("https://example.com/", 200), ("https://example.com/a", 200),
                        ("https://example.com/gone", 404)):
        snap.pages.append(Page(url=url, depth=1, status=status, html="<html></html>", content_type="text/html"))
    snap.status = "complete"
    return snap


GOOGLE_DATA = dict(
    sites=SITES,
    rows=[{"keys": ["https://example.com/"], "clicks": 5, "impressions": 100},
          {"keys": ["https://example.com/gone"], "clicks": 0, "impressions": 40}],
    sitemaps=[{"path": "https://example.com/sitemap.xml", "errors": "2", "warnings": "1", "isPending": False}],
    inspect={
        "https://example.com/": {"verdict": "PASS", "coverageState": "Submitted and indexed", "robotsTxtState": "ALLOWED",
                                 "indexingState": "INDEXING_ALLOWED", "pageFetchState": "SUCCESSFUL",
                                 "googleCanonical": "https://example.com/", "userCanonical": "https://example.com/"},
        "https://example.com/a": {"verdict": "FAIL", "coverageState": "Blocked by robots.txt",
                                  "robotsTxtState": "DISALLOWED", "indexingState": "INDEXING_ALLOWED",
                                  "pageFetchState": "SUCCESSFUL", "googleCanonical": "https://example.com/other",
                                  "userCanonical": "https://example.com/a"}})


@pytest.fixture
def verified(monkeypatch):
    state = make_session()
    state.last_verified = ("example.com", "sc-domain:example.com")
    monkeypatch.setattr(session, "SESSION", state)
    monkeypatch.setattr(probe_gsc, "_pause", lambda seconds: None)
    return state


async def run_probe(snap, google, monkeypatch):
    monkeypatch.setattr(api, "new_client", google.client)
    snap.extra["gsc"] = await probe_gsc.collect(None, snap, None)
    found, executed = run_checks(snap, snap.level, "standard")
    return [f for f in found if f.check_id.startswith("GSC-")], executed


async def test_level_2_collects_google_data_and_reports_the_findings(verified, monkeypatch):
    google = Google(**GOOGLE_DATA)
    found, executed = await run_probe(make_snap(), google, monkeypatch)
    assert pairs(found) == {("GSC-IDX-001", S.WARNING), ("GSC-IDX-001", S.NOTE), ("GSC-SMP-001", S.ERROR),
                            ("GSC-SMP-001", S.NOTE), ("GSC-PRF-001", S.WARNING), ("GSC-PRF-001", S.INFO)}
    assert all(executed[cid] == "ran" for cid in ("GSC-IDX-001", "GSC-SMP-001", "GSC-PRF-001"))
    assert len([b for b in google.bodies if "inspectionUrl" in b]) == 2  # die 404-Seite wird nicht inspiziert
    assert [b["dimensions"] for b in google.bodies if "dimensions" in b] == [["page"]]
    assert all(call[2] == "Bearer ACCESS-TOKEN-VALUE" for call in google.calls)
    assert all("example.com" in f.url for f in found)


async def test_level_1_uses_only_a_csv_import_and_never_calls_google(verified, monkeypatch):
    google = Google(**GOOGLE_DATA)
    verified.csv_pages = [{"url": "https://example.com/", "clicks": 5, "impressions": 100},
                          {"url": "https://example.com/gone", "clicks": 0, "impressions": 40}]
    found, executed = await run_probe(make_snap(level=1), google, monkeypatch)
    assert pairs(found) == {("GSC-PRF-001", S.WARNING), ("GSC-PRF-001", S.INFO)} and google.calls == []
    assert executed["GSC-IDX-001"] == "skipped:level2_required" and executed["GSC-SMP-001"] == "skipped:level2_required"
    verified.csv_pages = None
    found, executed = await run_probe(make_snap(level=1), google, monkeypatch)
    assert found == [] and executed["GSC-PRF-001"] == "skipped:no_gsc_data"


async def test_google_failures_are_never_reported_as_passed(verified, monkeypatch):
    found, executed = await run_probe(make_snap(), Google(status=403), monkeypatch)
    assert found == []
    assert executed["GSC-IDX-001"] == "skipped:gsc_inspection_unavailable"
    assert executed["GSC-SMP-001"] == "skipped:gsc_sitemaps_unavailable"
    assert executed["GSC-PRF-001"] == "skipped:no_gsc_data"


async def test_data_is_only_fetched_for_the_verified_domain_and_when_allowed(verified, monkeypatch):
    google = Google(**GOOGLE_DATA)
    verified.use_data = False
    await run_probe(make_snap(), google, monkeypatch)
    assert google.calls == []
    verified.use_data, verified.last_verified = True, ("other.test", "sc-domain:other.test")
    await run_probe(make_snap(), google, monkeypatch)
    assert google.calls == []


# ------------------------------------------------------------------ Speicher und Oberfläche

def test_memory_store_is_not_persistent_and_the_default_store_has_the_same_interface():
    store = MemoryStore()
    store.write("a", "b")
    assert store.read("a") == "b" and store.persistent is False
    store.delete("a")
    assert store.read("a") is None
    default = credstore.get_store()
    assert all(callable(getattr(default, name)) for name in ("read", "write", "delete"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-Anmeldeinformationsspeicher")
def test_windows_credential_manager_roundtrip():
    store = credstore.WindowsStore()
    name = "Claudios/test-" + secrets.token_hex(4)
    try:
        store.write(name, "wert-äöü")
        assert store.read(name) == "wert-äöü"
        store.write(name, "v2")
        assert store.read(name) == "v2"
    finally:
        store.delete(name)
    assert store.read(name) is None


def test_google_page_follows_the_session(qapp, monkeypatch):
    from claudios.ui import page_gsc

    state = Session(MemoryStore(persistent=True))
    monkeypatch.setattr(session, "SESSION", state)
    page = page_gsc.create(None)
    page.retranslate()
    assert page_gsc.NAV_KEY == "nav.gsc" and not page.level2.isEnabled() and not page.signin_btn.isEnabled()
    state.client = CLIENT
    state.set_tokens(oauth.Tokens("A", "R", time.time() + 3600), remember=False)
    state.sites = [SITES[0]]
    page.refresh()
    assert page.level2.isEnabled() and page.signout_btn.isEnabled() and page.signin_btn.isEnabled()
    assert page.sites.count() == 1
    page.shutdown()


def test_google_texts_exist_in_both_languages():
    keys = ["nav.gsc", "probe.gsc", "gsc.title", "gsc.intro", "gsc.status.in", "gsc.level2_ask", "gsc.csv_ok"]
    for lang in ("de", "en"):
        for key in keys:
            assert TEXTS[lang][key].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
