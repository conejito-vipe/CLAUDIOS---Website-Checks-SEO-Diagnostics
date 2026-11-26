"""Neue Prüfungen (Adress-Varianten, Barrierefreiheitserklärung, GPC, Sitemap-Abgleich, Bilder, Asset-Header,
Fremd-Domains, HTTP-Version, TLS-Ergänzungen, Tastatur, CMS, Seitengewicht, BIMI, DANE) und ihre Probe-Teile."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from claudios.core import probe_cms, probe_extra
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot


def page(html="<html><head></head><body><p>x</p></body></html>", url="https://example.com/", **kw):
    return Page(url=url, depth=0, status=200, html=html, content_type="text/html", **kw)


def snap_of(*pages, level=1, **extra):
    snap = Snapshot(target=normalize_input("example.com"), level=level, profile="standard")
    snap.pages.extend(pages or [page()])
    snap.status = "complete"
    snap.extra.update(extra)
    return snap


def run(snap, cid):
    found, executed = run_checks(snap, snap.level, "standard")
    return [f for f in found if f.check_id == cid], executed[cid]


def sev(found):
    return sorted(f.severity for f in found)


GOOD_EXTRA = {"skipped": False, "variants": {"host": "example.com", "alt": "www.example.com", "items": {}},
              "images": [], "assets": [], "gpc": {"declared": None, "hosts_with_signal": None},
              "foreign_domains": None}


def extra(**kw):
    return {"extra": {**GOOD_EXTRA, **kw}}


# ---------------------------------------------------------------- Adress-Varianten

PLAIN = "http" + ":" + "//"


def variants(**items):
    return extra(variants={"host": "example.com", "alt": "www.example.com", "items": items})


def test_a_plain_http_variant_that_serves_content_is_a_warning():
    found, state = run(snap_of(**variants(http={"status": 200, "location": ""})), "SEO-VAR-001")
    assert state == "ran" and sev(found) == [S.WARNING] and "https" in found[0].msg_en


def test_variants_that_redirect_permanently_are_fine_and_temporary_ones_are_a_note():
    ok = variants(http={"status": 301, "location": "https://example.com/"},
                  https_alt={"status": 308, "location": "https://example.com/"})
    assert run(snap_of(**ok), "SEO-VAR-001")[0] == []
    temp = variants(http={"status": 302, "location": "https://example.com/"})
    assert sev(run(snap_of(**temp), "SEO-VAR-001")[0]) == [S.NOTE]


def test_the_other_spelling_with_its_own_content_is_a_warning_and_nothing_reachable_is_skipped():
    found, _ = run(snap_of(**variants(https_alt={"status": 200, "location": ""})), "SEO-VAR-001")
    assert sev(found) == [S.WARNING]
    _, state = run(snap_of(**variants(http={"error": "net_timeout"})), "SEO-VAR-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Barrierefreiheitserklärung


def test_the_accessibility_statement_is_found_by_text_or_address():
    ok = page('<body><footer><a href="/erklaerung">Barrierefreiheitserklärung</a></footer></body>')
    assert run(snap_of(ok), "PRV-BFS-001")[0] == []
    by_url = page('<body><a href="/accessibility-statement">Info</a></body>')
    assert run(snap_of(by_url), "PRV-BFS-001")[0] == []


def test_a_missing_statement_is_info_and_a_note_for_a_shop():
    assert sev(run(snap_of(page("<body><a href='/x'>Start</a></body>")), "PRV-BFS-001")[0]) == [S.INFO]
    shop = page("<body><button>In den Warenkorb</button></body>")
    found, _ = run(snap_of(shop), "PRV-BFS-001")
    assert sev(found) == [S.NOTE] and "Shop" in found[0].msg_de


# ---------------------------------------------------------------- GPC

TRACKING = '<body><script src="https://www.googletagmanager.com/gtm.js"></script></body>'


def gpc(hosts, declared=None):
    return extra(gpc={"declared": declared, "hosts_with_signal": hosts})


def test_tracking_that_stays_with_the_gpc_signal_is_a_note():
    found, _ = run(snap_of(page(TRACKING), **gpc(["www.googletagmanager.com"])), "PRV-GPC-001")
    assert sev(found) == [S.NOTE] and "Google Tag Manager" in found[0].msg_de


def test_gpc_is_fine_when_tracking_disappears_is_declared_or_handled_in_script():
    assert run(snap_of(page(TRACKING), **gpc([])), "PRV-GPC-001")[0] == []
    assert run(snap_of(page(TRACKING), **gpc(["www.googletagmanager.com"], declared=True)), "PRV-GPC-001")[0] == []
    handled = page(TRACKING + "<script>if (navigator.globalPrivacyControl) {}</script>")
    assert run(snap_of(handled, **gpc(["www.googletagmanager.com"])), "PRV-GPC-001")[0] == []
    _, state = run(snap_of(page(TRACKING), **gpc(None)), "PRV-GPC-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Sitemap


def sitemap(urls, **kw):
    return {"sitemap": {"found": True, "urls": urls, "total": len(urls), "truncated": False, "index": False, **kw}}


def test_noindex_and_foreign_canonical_pages_in_the_sitemap_are_warnings():
    noindex = page('<head><meta name="robots" content="noindex"></head>', url="https://example.com/a")
    canon = page('<head><link rel="canonical" href="https://example.com/other"></head>', url="https://example.com/b")
    found, _ = run(snap_of(noindex, canon, **sitemap(["https://example.com/a", "https://example.com/b"])), "SEO-SMX-001")
    assert sev(found) == [S.WARNING, S.WARNING]


def test_pages_missing_from_the_sitemap_are_a_note_only_for_a_full_sitemap():
    pages = [page(url=f"https://example.com/p{i}") for i in range(6)]
    found, _ = run(snap_of(*pages, **sitemap(["https://example.com/p0"])), "SEO-SMX-001")
    assert sev(found) == [S.NOTE]
    assert run(snap_of(*pages, **sitemap(["https://example.com/p0"], truncated=True)), "SEO-SMX-001")[0] == []
    ok = [f"https://example.com/p{i}" for i in range(6)]
    assert run(snap_of(*pages, **sitemap(ok)), "SEO-SMX-001")[0] == []
    _, state = run(snap_of(page()), "SEO-SMX-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Bilder


def test_large_images_and_missing_dimensions_are_reported():
    html = "<body>" + "".join(f'<img src="/i{i}.jpg">' for i in range(8)) + "</body>"
    imgs = [{"url": "https://example.com/big.png", "status": 200, "type": "image/png", "length": 2_000_000},
            {"url": "https://example.com/mid.jpg", "status": 200, "type": "image/jpeg", "length": 200_000},
            {"url": "https://example.com/ok.webp", "status": 200, "type": "image/webp", "length": 200_000}]
    found, _ = run(snap_of(page(html), **extra(images=imgs)), "HTM-IMG-002")
    assert sorted(sev(found)) == sorted([S.WARNING, S.NOTE, S.NOTE, S.INFO])


def test_well_formed_images_give_no_finding():
    html = '<body><img src="a.webp" width="1" height="1"><img src="b.webp" width="1" height="1"></body>'
    assert run(snap_of(page(html), **extra()), "HTM-IMG-002")[0] == []


# ---------------------------------------------------------------- Asset-Header


def asset(**kw):
    base = {"url": "https://example.com/a.css", "kind": "css", "status": 200, "cache": "", "expires": False,
            "etag": False, "encoding": "", "length": 5000}
    return {**base, **kw}


def test_static_files_without_cache_or_compression_are_a_note():
    found, _ = run(snap_of(**extra(assets=[asset(), asset(url="https://example.com/b.js", kind="js")])), "SEO-ACH-001")
    assert sev(found) == [S.NOTE, S.NOTE]


def test_well_served_static_files_are_fine_and_short_cache_times_are_info():
    good = asset(cache="public, max-age=31536000, immutable", encoding="gzip")
    assert run(snap_of(**extra(assets=[good, good])), "SEO-ACH-001")[0] == []
    short = asset(cache="max-age=60", encoding="br")
    assert sev(run(snap_of(**extra(assets=[short])), "SEO-ACH-001")[0]) == [S.INFO]
    _, state = run(snap_of(**extra(assets=[])), "SEO-ACH-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Fremd-Domains


def foreign(days, statuses=()):
    when = (datetime.now(UTC) + timedelta(days=days)).isoformat()
    return extra(foreign_domains={"checked": [{"domain": "cdn.example", "expires": when, "statuses": list(statuses)}],
                                  "skip": None})


@pytest.mark.parametrize("days,statuses,expected", [(5, (), [S.ERROR]), (40, (), [S.NOTE]), (400, (), []),
                                                    (400, ("pendingdelete",), [S.ERROR])])
def test_script_domains_that_expire_soon_are_reported(days, statuses, expected):
    assert sev(run(snap_of(**foreign(days, statuses)), "SEC-SUP-001")[0]) == expected


def test_the_foreign_domain_check_needs_the_rdap_switch():
    _, state = run(snap_of(**extra(foreign_domains=None)), "SEC-SUP-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- HTTP-Version


def test_http_1_1_only_and_slow_answers_are_reported():
    slow = [page(url=f"https://example.com/{i}", elapsed_ms=3500) for i in range(3)]
    found, _ = run(snap_of(*slow, tls={"alpn": "http/1.1", "error": None}), "SEO-HTV-001")
    assert sorted(sev(found)) == [S.NOTE, S.WARNING]
    fast = [page(url=f"https://example.com/{i}", elapsed_ms=200) for i in range(3)]
    assert run(snap_of(*fast, tls={"alpn": "h2", "error": None}), "SEO-HTV-001")[0] == []


# ---------------------------------------------------------------- TLS-Ergänzungen


def test_hsts_preload_hint_and_certificate_names():
    hsts = page(headers={"strict-transport-security": "max-age=31536000; includeSubDomains"})
    found, _ = run(snap_of(hsts, tls={"san": ["example.com"], "error": None}), "TLS-EXT-001")
    assert sorted(sev(found)) == [S.INFO, S.NOTE]
    done = page(headers={"strict-transport-security": "max-age=63072000; includeSubDomains; preload"})
    assert run(snap_of(done, tls={"san": ["example.com", "*.example.com"], "error": None}), "TLS-EXT-001")[0] == []
    _, state = run(snap_of(done, tls={"error": "OSError"}), "TLS-EXT-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Tastatur


def test_removed_focus_outline_missing_skip_link_and_motion_are_reported():
    html = "<body><nav><a href='/a'>A</a></nav><main id='c'></main></body>"
    css = "a:focus { outline: none; } @keyframes x { from {opacity:0} to {opacity:1} }"
    found, _ = run(snap_of(page(html), assets={"css": [{"text": css, "status": 200}], "js": []}), "HTM-KEY-001")
    assert sorted(sev(found)) == [S.INFO, S.NOTE, S.WARNING]


def test_a_replacement_a_skip_link_and_reduced_motion_make_it_pass():
    html = "<body><a href='#c'>Skip</a><nav></nav><main id='c'></main></body>"
    css = ("a:focus { outline: none; box-shadow: 0 0 0 2px blue; } @keyframes x {} "
           "@media (prefers-reduced-motion: reduce) { * { animation: none } }")
    assert run(snap_of(page(html), assets={"css": [{"text": css, "status": 200}], "js": []}), "HTM-KEY-001")[0] == []
    focus_visible = "a:focus { outline: none } a:focus-visible { outline: 2px solid red }"
    assert run(snap_of(page(html), assets={"css": [{"text": focus_visible, "status": 200}], "js": []}), "HTM-KEY-001")[0] == []


# ---------------------------------------------------------------- CMS


def test_cms_paths_are_reported_and_need_level_2():
    cms = {"cms": "wordpress", "total": 2, "errors": 0, "hits": [{"path": "wp-json/wp/v2/users", "kind": "users"}]}
    found, _ = run(snap_of(level=2, cms=cms), "SEC-CMX-001")
    assert sev(found) == [S.WARNING]
    _, state = run(snap_of(level=2), "SEC-CMX-001")
    assert state.startswith("skipped")
    cms["errors"] = 2
    _, state = run(snap_of(level=2, cms=cms), "SEC-CMX-001")
    assert state.startswith("skipped")


def test_cms_detection():
    assert probe_cms.detect_cms('<link href="/wp-content/x.css">') == "wordpress"
    assert probe_cms.detect_cms('<meta name="generator" content="Joomla! - Open Source">') == "joomla"
    assert probe_cms.detect_cms("<p>hi</p>") is None


# ---------------------------------------------------------------- Seitengewicht


def test_page_weight_blocking_scripts_and_foreign_servers():
    head = "".join(f'<script src="/s{i}.js"></script>' for i in range(5))
    foreign_tags = "".join(f'<img src="https://cdn{i}.other{i}.com/a.png">' for i in range(11))
    big = page(f"<html><head>{head}</head><body>{foreign_tags}</body></html>", size=1_200_000)
    assert sorted(sev(run(snap_of(big), "SEO-WGT-001")[0])) == [S.NOTE, S.NOTE, S.WARNING]
    assert run(snap_of(page(size=1000)), "SEO-WGT-001")[0] == []


# ---------------------------------------------------------------- BIMI und DANE


def dns(**records):
    return {"dns": {"records": {"mx": ["10 mail.example.com."], "ns": ["ns"], "txt": [], **records}}}


def test_bimi_is_info_when_dmarc_is_enforced_but_no_record_exists():
    enforced = ['"v=DMARC1; p=reject"']
    assert sev(run(snap_of(**dns(dmarc=enforced, bimi=[])), "DNS-BIM-001")[0]) == [S.INFO]
    assert run(snap_of(**dns(dmarc=enforced, bimi=['"v=BIMI1; l=https://x/l.svg"'])), "DNS-BIM-001")[0] == []
    assert run(snap_of(**dns(dmarc=['"v=DMARC1; p=none"'], bimi=[])), "DNS-BIM-001")[0] == []


def test_dane_is_reported_only_with_dnssec_and_a_record():
    assert sev(run(snap_of(**dns(ds=["1 2 3"], tlsa=["3 1 1 abcd"])), "DNS-DAN-001")[0]) == [S.INFO]
    assert run(snap_of(**dns(ds=[], tlsa=["3 1 1 abcd"])), "DNS-DAN-001")[0] == []
    _, state = run(snap_of(**dns(ds=None, tlsa=None)), "DNS-DAN-001")
    assert state.startswith("skipped")


# ---------------------------------------------------------------- Probe-Teile


def test_alt_host_and_external_hosts():
    assert probe_extra.alt_host("example.com", "example.com") == "www.example.com"
    assert probe_extra.alt_host("www.example.com", "example.com") == "example.com"
    assert probe_extra.alt_host("shop.example.com", "example.com") is None
    html = ('<script src="https://cdn.other.com/a.js"></script><img src="/local.png">'
            '<link rel="stylesheet" href="https://fonts.x.org/c.css"><link rel="icon" href="https://i.z.org/i.png">')
    assert probe_extra.external_hosts(html, "https://example.com/", "example.com", "example.com") == ["cdn.other.com", "fonts.x.org"]


class FakeGk:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    async def fetch(self, url, **kw):
        self.calls.append((url, kw))
        res = self.responses.get(url)
        if isinstance(res, ClaudiosError):
            raise res
        return res or Response(url, 404, {}, [], b"", False, 1)


def resp(url, status, headers=None, body=b""):
    return Response(url, status, headers or {}, [], body, False, 1)


def test_the_variant_probe_uses_plain_http_only_without_following_redirects():
    gk = FakeGk({PLAIN + "example.com/": resp(PLAIN + "example.com/", 301, {"location": "https://example.com/"}),
                 "https://www.example.com/": resp("https://www.example.com/", 200)})
    data = asyncio.run(probe_extra._variants(gk, snap_of()))
    assert data["items"]["http"] == {"status": 301, "location": "https://example.com/"}
    assert data["items"]["https_alt"]["status"] == 200
    for url, kw in gk.calls:
        assert kw["follow"] is False and kw.get("plain", False) == url.startswith(PLAIN)


def test_the_gpc_probe_sends_only_the_gpc_header_and_reads_the_declaration():
    gk = FakeGk({"https://example.com/.well-known/gpc.json": resp("u", 200, body=b'{"gpc": true, "lastUpdate": "x"}'),
                 "https://example.com/": resp("https://example.com/", 200, body=b'<script src="https://t.example.net/a.js"></script>')})
    data = asyncio.run(probe_extra._gpc(gk, snap_of()))
    assert data == {"declared": True, "hosts_with_signal": ["t.example.net"]}
    assert gk.calls[1][1]["headers"] == {"Sec-GPC": "1"}


def test_the_cms_probe_stores_only_paths_and_kinds():
    html = '<link href="/wp-content/a.css">'
    gk = FakeGk({"https://example.com/wp-json/wp/v2/users": resp("u", 200, body=b'[{"id":1,"slug":"admin"}]'),
                 "https://example.com/xmlrpc.php": resp("u", 405, body=b"XML-RPC server accepts POST requests only")})
    data = asyncio.run(probe_cms.collect(gk, snap_of(page(html), level=2), None))
    assert {h["kind"] for h in data["hits"]} == {"xmlrpc", "users"} and "body" not in str(data)
    assert all(kw["follow"] is False and url.startswith("https://") for url, kw in gk.calls)  # nie Weiterleitungen, nur HTTPS
    assert asyncio.run(probe_cms.collect(gk, snap_of(level=2), None)) is None
