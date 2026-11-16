from urllib.parse import urlsplit

from claudios.core.adsprobe import fetch_ads
from claudios.core.engine import run_checks
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot
from claudios.core.takeoverprobe import collect_takeover

SHOP = """<!doctype html><html lang="en"><head><title>Shop</title>
<meta name="generator" content="WordPress 6.4.2"><script src="/wp-content/x.js"></script></head><body>
<form><input type="password" name="p"></form>
<p>Contact: info@shop.test and logo@2x.png</p><a href="mailto:sales@shop.test">mail</a></body></html>"""

AD_PAGE = ('<html><head><script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js">'
           "</script></head></html>")


def make_snap(html="<html></html>", headers=None, url="https://example.com/", **kw):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url=url, depth=1, status=200, headers=headers or {}, html=html,
                           content_type="text/html; charset=utf-8", **kw))
    snap.status = "complete"
    return snap


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def test_hardening_checks_find_planted_problems():
    headers = {"access-control-allow-origin": "*", "access-control-allow-credentials": "true",
               "cache-control": "public, max-age=3600",
               "content-security-policy": "default-src 'self'; frame-ancestors 'self'"}
    found, _ = run_checks(make_snap(SHOP, headers), 1, "standard")
    got = pairs(found)
    assert ("SEC-COR-001", S.ERROR) in got
    assert ("SEC-CCH-001", S.WARNING) in got
    assert ("SEC-CSR-001", S.INFO) in got
    assert ("SEC-EML-001", S.INFO) in got
    assert ("SEC-CMS-001", S.NOTE) in got
    mail = next(f for f in found if f.check_id == "SEC-EML-001")
    assert "2 e-mail" in mail.msg_en.lower()
    cms = next(f for f in found if f.check_id == "SEC-CMS-001")
    assert "6.4.2" in cms.msg_en
    assert all("info@shop.test" not in f.evidence for f in found)


def test_clean_page_has_no_hardening_findings():
    headers = {"content-security-policy": "default-src 'self'; frame-ancestors 'self'; report-to csp",
               "cache-control": "no-store"}
    found, _ = run_checks(make_snap("<html><body><p>Hello</p></body></html>", headers), 1, "standard")
    prefixes = ("SEC-COR", "SEC-CCH", "SEC-CSR", "SEC-EML", "SEC-CMS")
    assert [f for f in found if f.check_id.startswith(prefixes)] == []


def test_cors_null_origin_warns_and_specific_origin_is_fine():
    found, _ = run_checks(make_snap(headers={"access-control-allow-origin": "null"}), 1, "standard")
    assert ("SEC-COR-001", S.WARNING) in pairs(found)
    found, _ = run_checks(make_snap(headers={"access-control-allow-origin": "https://partner.example"}), 1,
                          "standard")
    assert not [f for f in found if f.check_id == "SEC-COR-001"]


def test_login_path_without_no_store_gets_a_note():
    found, _ = run_checks(make_snap(url="https://example.com/konto"), 1, "standard")
    assert ("SEC-CCH-001", S.NOTE) in pairs(found)
    found, _ = run_checks(make_snap(url="https://example.com/konto", headers={"cache-control": "no-store"}), 1,
                          "standard")
    assert not [f for f in found if f.check_id == "SEC-CCH-001"]


class FakeResolver:
    def __init__(self, zone):
        self.zone = zone

    async def query(self, name, rtype):
        return list(self.zone.get((name, rtype), []))


async def test_takeover_finds_dangling_cnames():
    snap = make_snap('<script src="https://assets.example.com/a.js"></script>')
    snap.pages[0].external_links = ["https://blog.example.com/x", "https://shop.example.com/", "https://other.org/"]
    zone = {
        ("blog.example.com", "CNAME"): ["old-app.azurewebsites.net."],
        ("shop.example.com", "CNAME"): ["shops.myshopify.com."],
        ("shops.myshopify.com", "A"): ["23.227.38.65"],
        ("assets.example.com", "CNAME"): ["cdn.unknown-provider.example."],
    }
    snap.extra["takeover"] = await collect_takeover(FakeResolver(zone), snap)
    assert snap.extra["takeover"]["hosts"] == 3
    found, executed = run_checks(snap, 1, "standard")
    tko = [f for f in found if f.check_id == "TKO-DNS-001"]
    assert len(tko) == 2 and {f.severity for f in tko} == {S.ERROR, S.WARNING}
    assert any("azurewebsites" in f.evidence for f in tko)
    assert executed["TKO-DNS-001"] == "ran"


def test_takeover_and_ads_are_skipped_without_probe_data():
    _, executed = run_checks(make_snap(), 1, "standard")
    assert executed["TKO-DNS-001"] == "skipped:no_takeover_data"
    assert executed["ADS-TXT-001"] == "skipped:no_ads_data"


class FakeGK:
    cancel = None

    def __init__(self, responses):
        self.responses, self.calls = responses, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        path = urlsplit(url).path
        self.calls.append(path)
        status, ctype, body = self.responses.get(path, (404, "text/html", ""))
        return Response(url, status, {"content-type": ctype}, [], body.encode(), False, 1)


async def ads_run(responses, html=AD_PAGE):
    snap = make_snap(html)
    gk = FakeGK(responses)
    snap.extra["ads"] = await fetch_ads(gk, snap)
    found, executed = run_checks(snap, 1, "standard")
    return [f for f in found if f.check_id == "ADS-TXT-001"], gk.calls, executed


async def test_ads_missing_file_is_a_warning():
    found, calls, executed = await ads_run({})
    assert [f.severity for f in found] == [S.WARNING]
    assert calls == ["/ads.txt", "/app-ads.txt"] and executed["ADS-TXT-001"] == "ran"


async def test_ads_invalid_lines_are_counted_and_variables_are_allowed():
    text = "google.com, pub-1, DIRECT, f08c\nbadline\n# comment\ncontact=a@b.example\n"
    found, _, _ = await ads_run({"/ads.txt": (200, "text/plain", text)})
    assert [f.severity for f in found] == [S.NOTE]
    assert "1 invalid" in found[0].msg_en


async def test_ads_html_instead_of_text_is_a_warning():
    found, _, _ = await ads_run({"/ads.txt": (200, "text/html; charset=utf-8", "<html>Not found</html>")})
    assert [f.severity for f in found] == [S.WARNING]


async def test_no_ads_means_no_requests_and_no_findings():
    found, calls, executed = await ads_run({}, html="<html></html>")
    assert found == [] and calls == [] and executed["ADS-TXT-001"] == "ran"