import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from claudios.checks import _schema
from claudios.core import (
    apikeys,
    options,
    probe_psi,
    probe_safebrowsing,
    probe_shots,
    services,
    thirdparty,
)
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.snapshot import Page, Snapshot
from claudios.core.toolbudget import classify
from claudios.gsc.credstore import MemoryStore
from claudios.i18n.strings import TEXTS, get_lang, set_lang
from claudios.report import shots

KEY = "k" * 30


def page(html="<html></html>", url="https://example.com/", depth=1, **kw):
    return Page(url=url, depth=depth, status=200, html=html, content_type="text/html; charset=utf-8", **kw)


def snap_of(*pages):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.extend(pages or [page()])
    snap.status = "complete"
    return snap


def run(snap, cid):
    found, executed = run_checks(snap, 1, "standard")
    return [f for f in found if f.check_id == cid], executed[cid]


def sevs(found):
    return sorted(f.severity for f in found)


def ld(data):
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setitem(apikeys._STATE, "store", MemoryStore())
    return tmp_path


def test_api_keys_are_validated_stored_and_deleted(env):
    assert apikeys.has_key("safebrowsing") is False
    for bad in ("", "short", "has space " + "x" * 20, "ü" * 30):
        with pytest.raises(ValueError):
            apikeys.set_key("safebrowsing", bad)
    apikeys.set_key("safebrowsing", f"  {KEY}  ")
    assert apikeys.get("safebrowsing") == KEY and apikeys.has_key("safebrowsing")
    apikeys.delete("safebrowsing")
    assert apikeys.get("safebrowsing") is None
    with pytest.raises(ValueError):
        apikeys.get("other")


def test_switches_and_options_are_off_by_default_and_know_only_their_names(env):
    for name in services.KNOWN:
        assert services.enabled(name) is False
    services.set_enabled("pagespeed", True)
    assert services.enabled("pagespeed") and not services.enabled("safebrowsing")
    assert options.enabled("screenshots") is False
    options.set_enabled("screenshots", True)
    assert options.enabled("screenshots") is True
    with pytest.raises(ValueError):
        options.set_enabled("other", True)


async def test_third_party_client_only_reaches_the_fixed_google_hosts():
    for url in ("https://evil.example/x", "https://www.googleapis.com:8443/x", "https://user:pw@www.googleapis.com/x",
                "http" + "://www.googleapis.com/x"):
        with pytest.raises(ClaudiosError) as error:
            await thirdparty.request("GET", url, max_bytes=10, timeout=5)
        assert error.value.code == E.INPUT_INVALID
    with pytest.raises(ClaudiosError):
        await thirdparty.request("DELETE", "https://www.googleapis.com/x", max_bytes=10, timeout=5)


async def test_third_party_client_caps_the_body_and_sends_json():
    seen = {}

    def handler(request):
        seen["host"], seen["body"] = request.url.host, request.content
        return httpx.Response(200, content=b"x" * 100)

    status, body, truncated = await thirdparty.request(
        "POST", "https://safebrowsing.googleapis.com/v4/x", json_body={"a": 1}, max_bytes=10, timeout=5,
        transport=httpx.MockTransport(handler))
    assert status == 200 and len(body) == 10 and truncated
    assert seen["host"] == "safebrowsing.googleapis.com" and json.loads(seen["body"]) == {"a": 1}


async def test_third_party_client_maps_failures_to_codes_without_leaking_the_url():
    def broken(request):
        raise httpx.ConnectError("boom " + str(request.url))

    with pytest.raises(ClaudiosError) as error:
        await thirdparty.request("GET", "https://www.googleapis.com/a?key=SECRETKEY", max_bytes=10, timeout=5,
                                 transport=httpx.MockTransport(broken))
    assert error.value.code == E.NET_CONNECT and "SECRETKEY" not in str(error.value)


def test_safe_browsing_urls_are_clean_unique_and_limited():
    pages = [page(url=f"https://example.com/p{i}?token=abc#x") for i in range(10)]
    urls = probe_safebrowsing.urls_to_check(snap_of(*pages))
    assert len(urls) == LIMITS.safebrowsing_urls_max and urls[0] == "https://example.com/"
    assert all("?" not in u and "#" not in u for u in urls) and len(set(urls)) == len(urls)


async def test_safe_browsing_does_nothing_without_switch_or_key(env):
    gk = SimpleNamespace(cancel=None)
    assert await probe_safebrowsing.collect(gk, snap_of(), None) == {"enabled": False, "skip": "safebrowsing_disabled"}
    services.set_enabled("safebrowsing", True)
    assert (await probe_safebrowsing.collect(gk, snap_of(), None))["skip"] == "safebrowsing_no_key"


async def test_safe_browsing_sends_the_key_only_as_a_parameter_and_reports_matches(env, monkeypatch):
    services.set_enabled("safebrowsing", True)
    apikeys.set_key("safebrowsing", KEY)
    calls = []

    async def fake(method, url, **kw):
        calls.append((method, url, kw))
        answer = {"matches": [{"threatType": "MALWARE", "threat": {"url": "https://example.com/?token=abc"}}]}
        return 200, json.dumps(answer).encode(), False

    monkeypatch.setattr(thirdparty, "request", fake)
    data = await probe_safebrowsing.collect(SimpleNamespace(cancel=None), snap_of(), None)
    assert data["skip"] is None and data["matches"][0]["type"] == "MALWARE" and "abc" not in data["matches"][0]["url"]
    method, url, kw = calls[0]
    assert method == "POST" and KEY not in json.dumps(kw["json_body"]) and kw["params"] == {"key": KEY}
    found, state = run(_with(snap_of(), safebrowsing=data), "SEC-SBR-001")
    assert state == "ran" and sevs(found) == [S.CRITICAL] and KEY not in repr(found)


async def test_safe_browsing_failures_become_a_reason(env, monkeypatch):
    services.set_enabled("safebrowsing", True)
    apikeys.set_key("safebrowsing", KEY)
    for answer, reason in (((403, b"{}", False), "safebrowsing_http_403"), ((200, b"{}", True), "safebrowsing_too_large"),
                           ((200, b"[", False), "safebrowsing_unreadable")):
        async def fake(method, url, answer=answer, **kw):
            return answer

        monkeypatch.setattr(thirdparty, "request", fake)
        assert (await probe_safebrowsing.collect(SimpleNamespace(cancel=None), snap_of(), None))["skip"] == reason

    async def down(method, url, **kw):
        raise ClaudiosError(E.NET_TIMEOUT, url="x")

    monkeypatch.setattr(thirdparty, "request", down)
    assert (await probe_safebrowsing.collect(SimpleNamespace(cancel=None), snap_of(), None))["skip"] == "safebrowsing_unreachable"
    assert run(snap_of(), "SEC-SBR-001")[1] == "skipped:no_safebrowsing_data"


def _with(snap, **extra):
    snap.extra.update(extra)
    return snap


PSI_ANSWER = {
    "lighthouseResult": {
        "categories": {"performance": {"score": 0.42}, "seo": {"score": 0.95}, "accessibility": {"score": 0.8},
                       "best-practices": {"score": 1}},
        "audits": {"largest-contentful-paint": {"numericValue": 4200.4}, "cumulative-layout-shift": {"numericValue": 0.12345}}},
    "loadingExperience": {"overall_category": "SLOW", "metrics": {
        "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 4100, "category": "SLOW"},
        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5, "category": "FAST"},
        "INTERACTION_TO_NEXT_PAINT": {"percentile": 300, "category": "AVERAGE"}}},
}


def test_psi_parsing_is_defensive():
    parsed = probe_psi.parse(PSI_ANSWER)
    assert parsed["scores"] == {"performance": 42, "seo": 95, "accessibility": 80, "best_practices": 100}
    assert parsed["lab"] == {"lcp_ms": 4200, "cls": 0.123} and parsed["overall"] == "SLOW"
    assert parsed["field"]["LARGEST_CONTENTFUL_PAINT_MS"] == {"percentile": 4100.0, "category": "SLOW"}
    for junk in (None, [], {}, {"lighthouseResult": 5}, {"lighthouseResult": {"categories": {"performance": {"score": 7}}}}):
        assert probe_psi.parse(junk) is None


async def test_psi_probe_and_check(env, monkeypatch):
    gk = SimpleNamespace(cancel=None)
    assert await probe_psi.collect(gk, snap_of(), None) == {"enabled": False, "skip": "psi_disabled"}
    services.set_enabled("pagespeed", True)
    calls = []

    async def fake(method, url, **kw):
        calls.append((method, url, kw))
        return 200, json.dumps(PSI_ANSWER).encode(), False

    monkeypatch.setattr(thirdparty, "request", fake)
    data = await probe_psi.collect(gk, snap_of(), None)
    assert calls[0][0] == "GET" and ("strategy", "mobile") in calls[0][2]["params"] and len(calls) == 1
    found, state = run(_with(snap_of(), psi=data), "SEO-PSI-001")
    assert state == "ran" and S.WARNING in {f.severity for f in found} and S.NOTE in {f.severity for f in found}
    assert any("LCP" in f.msg_en for f in found if f.severity == S.WARNING)

    async def limited(method, url, **kw):
        return 429, b"{}", False

    monkeypatch.setattr(thirdparty, "request", limited)
    assert (await probe_psi.collect(gk, snap_of(), None))["skip"] == "psi_http_429"
    assert run(snap_of(), "SEO-PSI-001")[1] == "skipped:no_psi_data"
    assert run(_with(snap_of(), psi={"enabled": True, "skip": "psi_http_429"}), "SEO-PSI-001")[1] == "skipped:psi_http_429"


def test_psi_without_field_data_is_only_an_info():
    data = {"enabled": True, "skip": None, "scores": {"performance": 95}, "lab": {}, "field": {}, "overall": None}
    found, state = run(_with(snap_of(), psi=data), "SEO-PSI-001")
    assert state == "ran" and sevs(found) == [S.INFO]


def test_the_screenshot_script_and_budget_rules():
    script = Path(probe_shots.__file__).parent.parent / "components" / "npm" / "shot_probe.js"
    text = script.read_text("utf-8")
    assert "--host-resolver-rules" in text and 'serviceWorkers: "block"' in text and "isLocalName" in text
    assert "ignoreHTTPSErrors" not in text
    assert classify(["node", "C:\\x\\shot_probe.js", "in.json"]) == "browser"


def _fake_run_tool(args, **kwargs):
    payload = json.loads(Path(args[2]).read_text("utf-8"))
    out = Path(payload["outdir"])
    (out / "desktop.png").write_bytes(b"\x89PNG" + b"0" * 100)
    Path(args[3]).write_text(json.dumps({"browser": "x", "error": None, "shots": [
        {"view": "desktop", "file": "desktop.png", "error": None}, {"view": "mobile", "file": None, "error": "x"},
        {"view": "evil", "file": "../evil.png", "error": None}]}), "utf-8")


async def test_screenshots_run_only_with_the_option_and_are_listed_and_zipped(env, monkeypatch):
    gk = SimpleNamespace(cancel=None)
    assert await probe_shots.collect(gk, snap_of(), None) == {"enabled": False, "skip": "shots_disabled"}
    options.set_enabled("screenshots", True)
    monkeypatch.setattr(probe_shots, "_node", lambda: Path("/t/node/node.exe"))
    monkeypatch.setattr(probe_shots, "_pin", lambda snap: "93.184.216.34")
    monkeypatch.setattr(probe_shots, "_environment", lambda node: {})
    monkeypatch.setattr(probe_shots, "run_tool", _fake_run_tool)
    old = probe_shots.shots_root() / "20200101T000000000000_old.test"
    old.mkdir(parents=True)
    for index in range(LIMITS.shots_keep):
        (probe_shots.shots_root() / f"2020010{index + 2}T000000000000_old.test").mkdir()
    data = await probe_shots.collect(gk, snap_of(), None)
    assert data["skip"] is None and data["files"] == ["desktop.png"] and Path(data["dir"]).is_dir()
    assert not old.exists()  # ältere Ordner werden aufgeräumt
    assert len([p for p in probe_shots.shots_root().iterdir() if p.is_dir()]) <= LIMITS.shots_keep
    result = SimpleNamespace(snapshot=_with(snap_of(), shots=data))
    assert [p.name for p in shots.files_of(result)] == ["desktop.png"]
    out = shots.build_zip(result, env / "s.zip")
    with zipfile.ZipFile(out) as archive:
        assert sorted(archive.namelist()) == ["desktop.png", "manifest.json"]


async def test_screenshot_failures_and_foreign_folders_are_never_trusted(env, monkeypatch):
    options.set_enabled("screenshots", True)
    monkeypatch.setattr(probe_shots, "_node", lambda: None)
    assert (await probe_shots.collect(SimpleNamespace(cancel=None), snap_of(), None))["skip"] == "tool_not_found"
    foreign = env / "elsewhere"
    foreign.mkdir()
    (foreign / "desktop.png").write_bytes(b"x")
    fake = SimpleNamespace(snapshot=_with(snap_of(), shots={"skip": None, "dir": str(foreign), "files": ["desktop.png"]}))
    assert shots.files_of(fake) == []
    with pytest.raises(ClaudiosError):
        shots.build_zip(fake, env / "x.zip")


def test_schema_depth_and_shop_quality():
    thin = ld({"@context": "https://schema.org", "@graph": [
        {"@type": "Product", "name": "A", "offers": {"@type": "Offer", "price": "5", "priceCurrency": "euro"},
         "aggregateRating": {"ratingValue": "4"}},
        {"@type": "Article", "headline": "H"}]})
    found, state = run(snap_of(page(f"<html><body>{thin}</body></html>")), "SEO-SCH-001")
    assert state == "ran" and sevs(found) == [S.NOTE] * 3
    assert any("author" in f.msg_en for f in found) and any("availability" in f.msg_en for f in found)
    found, _ = run(snap_of(page(f"<html><body>{thin}</body></html>")), "SEO-ECO-001")
    assert {f.severity for f in found} == {S.NOTE, S.INFO} and any("currency" in f.msg_en for f in found)
    assert any("terms" in f.msg_en for f in found)
    assert run(snap_of(), "SEO-SCH-001") == ([], "ran") and run(snap_of(), "SEO-ECO-001") == ([], "ran")


def test_trust_signals_geo_and_local_seo():
    text = "word " * 450
    article = f"<html><body><h2>Was ist das?</h2><p>{text}</p></body></html>"
    found, _ = run(snap_of(page(article)), "SEO-EEA-001")
    assert sevs(found) == [S.INFO] and "author byline" in found[0].msg_en
    good = (f'<html><body><a href="/about">About us</a><a href="/kontakt">Kontakt</a><a href="/impressum">Impressum</a>'
            f'<span class="author">A</span><time datetime="2025-01-01">x</time><p>{text}</p></body></html>')
    assert run(snap_of(page(good)), "SEO-EEA-001")[0] == []
    # 450 Wörter liegen unter der Grenze von 600: nur Frage ohne FAQPage und Startseite ohne Organization
    assert len(run(snap_of(page(article)), "SEO-GEO-001")[0]) == 2
    long_article = f"<html><body><h2>Was ist das?</h2><p>{'word ' * 700}</p></body></html>"
    found, _ = run(snap_of(page(long_article)), "SEO-GEO-001")
    assert len(found) == 3 and {f.severity for f in found} == {S.INFO}
    local = ld({"@type": "Restaurant", "name": "Chez", "telephone": "+49 30 1234567",
                "address": {"@type": "PostalAddress", "streetAddress": "Weg 1"}})
    found, _ = run(snap_of(page(f"<html><body>{local}</body></html>")), "SEO-LOC-001")
    assert sevs(found) == [S.INFO, S.NOTE] and any("postalCode" in f.msg_en for f in found)
    phones = "".join(f'<a href="tel:+49 30 {n}{n}{n}{n}{n}{n}">x</a>' for n in range(1, 5))
    found, _ = run(snap_of(page(f"<html><body><address>x</address>{phones}</body></html>")), "SEO-LOC-001")
    assert len(found) == 2 and {f.severity for f in found} == {S.INFO}


def test_international_seo_and_consent_quality():
    html = ('<html lang="de"><head><link rel="alternate" hreflang="en" href="https://example.com/">'
            '<link rel="alternate" hreflang="us" href="https://example.com/us/">'
            '<link rel="canonical" href="https://example.com/other"></head></html>')
    found, state = run(snap_of(page(html, headers={"content-language": "fr"})), "SEO-INT-001")
    assert state == "ran" and S.WARNING in {f.severity for f in found} and len(found) == 4
    assert run(snap_of(page('<html lang="en"></html>')), "SEO-INT-001")[0] == []
    assert sevs(run(snap_of(page('<html lang="e!"></html>')), "SEO-INT-001")[0]) == [S.NOTE]
    banner = ('<div id="cookie-banner"><p>Wir nutzen Cookies</p><button>Alle akzeptieren</button>'
              '<input type="checkbox" name="marketing" checked></div>')
    found, state = run(snap_of(page(f"<html><body>{banner}</body></html>")), "PRV-CNS-001")
    assert state == "ran" and sevs(found) == [S.INFO, S.NOTE, S.NOTE]
    fair = ('<div class="cookie-consent"><button>Alle akzeptieren</button><button>Nur notwendige</button>'
            '<a href="/datenschutz">Datenschutz</a></div>')
    assert run(snap_of(page(f"<html><body>{fair}</body></html>")), "PRV-CNS-001")[0] == []
    assert run(snap_of(page('<html><body><a href="/cookies">Cookies</a></body></html>')), "PRV-CNS-001")[0] == []


def test_schema_helpers_ignore_broken_and_huge_blocks():
    broken = '<script type="application/ld+json">{not json}</script>'
    huge = '<script type="application/ld+json">' + " " * (_schema.MAX_BLOCK + 1) + "</script>"
    assert _schema.items(page(f"<html>{broken}{huge}</html>")) == []
    item = {"@type": ["https://schema.org/LocalBusiness", "schema:Store"]}
    assert _schema.types_of(item) == {"localbusiness", "store"}


def test_texts_exist_in_both_languages_and_format_cleanly():
    keys = [k for k in TEXTS["de"] if k.startswith("svc.")] + [f"probe.{n}" for n in ("safebrowsing", "psi", "shots")]
    assert len(keys) >= 30
    for key in keys:
        for lang in ("de", "en"):
            assert TEXTS[lang][key].strip()
    assert "{path}" not in TEXTS["de"]["svc.shots.zip"] and set(TEXTS["de"]) == set(TEXTS["en"])


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_services_page_asks_stores_the_key_and_exports_screenshots(qapp, env, monkeypatch):
    from claudios.ui import page_services

    old = get_lang()
    try:
        set_lang("de")
        page_obj = page_services.create(None)
        page_obj.retranslate()
        assert not page_obj.sb.isChecked() and not page_obj.sb_delete.isEnabled() and "kein Schlüssel" in page_obj.sb_state.text()
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: False)
        page_obj.sb.setChecked(True)
        page_obj.psi.setChecked(True)
        page_obj.shots.setChecked(True)
        assert not (services.enabled("safebrowsing") or services.enabled("pagespeed") or options.enabled("screenshots"))
        monkeypatch.setattr(page_services, "_confirm", lambda parent, text: True)
        page_obj.sb.setChecked(True)
        page_obj.psi.setChecked(True)
        page_obj.shots.setChecked(True)
        assert services.enabled("safebrowsing") and services.enabled("pagespeed") and options.enabled("screenshots")
        warnings = []
        monkeypatch.setattr(page_services, "_warn", lambda parent, text: warnings.append(text))
        page_obj.sb_key.setText("short")
        page_obj.save_key()
        assert warnings and not apikeys.has_key("safebrowsing")
        page_obj.sb_key.setText(KEY)
        page_obj.save_key()
        assert apikeys.has_key("safebrowsing") and page_obj.sb_key.text() == "" and page_obj.sb_delete.isEnabled()
        page_obj.delete_key()
        assert not apikeys.has_key("safebrowsing")
        infos = []
        monkeypatch.setattr(page_services, "_info", lambda parent, text: infos.append(text))
        page_obj.export_shots()
        assert infos == [TEXTS["de"]["svc.shots.none"]]
    finally:
        set_lang(old)
