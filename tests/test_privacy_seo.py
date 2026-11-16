from urllib.parse import urlsplit

from claudios.checks._util import F, group_digits
from claudios.core.engine import run_checks
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.probes import gather_probes
from claudios.core.seoprobe import collect_sitemap, probe_soft404
from claudios.core.snapshot import Page, Snapshot, parse_set_cookie

HOME_DE = """<!doctype html><html lang="de"><head><title>Startseite der Firma</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto">
<script>(function(w,d){var j=d.createElement('script');j.src='https://www.googletagmanager.com/gtm.js';})(window,document);</script>
</head><body><iframe src="https://www.youtube.com/embed/abc"></iframe><a href="/kontakt">Kontakt</a></body></html>"""

GOOD_DE = ('<!doctype html><html lang="de"><head><title>Firma</title>'
           '<script src="https://consent.cookiebot.com/uc.js"></script>'
           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto"></head><body>'
           '<a href="/impressum">Impressum</a> <a href="/datenschutz">Datenschutzerklärung</a></body></html>')

OG_FULL = ('<!doctype html><html lang="en"><head><title>Page</title><meta property="og:title" content="T">'
           '<meta property="og:description" content="D"><meta property="og:image" content="https://example.com/i.png">'
           '<meta name="twitter:card" content="summary">'
           '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"X"}'
           "</script></head></html>")


def page(html="<html></html>", url="https://example.com/", depth=1, **kw):
    return Page(url=url, depth=depth, status=200, html=html, content_type="text/html; charset=utf-8", **kw)


def make_snap(pages):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.extend(pages)
    snap.status = "complete"
    return snap


def findings(snap, prefix):
    found, executed = run_checks(snap, 1, "standard")
    return [f for f in found if f.check_id.startswith(prefix)], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


def test_privacy_flags_trackers_missing_legal_links_and_missing_consent():
    cookies = [parse_set_cookie("_ga=GA1.2.3; Path=/"), parse_set_cookie("lang=de; Path=/")]
    found, _ = findings(make_snap([page(HOME_DE, cookies=cookies)]), "PRV-")
    got = pairs(found)
    assert ("PRV-LEG-001", S.WARNING) in got
    assert ("PRV-EXT-001", S.WARNING) in got and ("PRV-EXT-001", S.NOTE) in got
    assert ("PRV-CMP-001", S.WARNING) in got
    assert ("PRV-COK-001", S.WARNING) in got and ("PRV-COK-001", S.INFO) in got
    assert any("Google Fonts" in f.msg_en for f in found)
    assert all("GA1.2.3" not in f.evidence for f in found)


def test_consent_solution_and_legal_links_are_recognised():
    found, _ = findings(make_snap([page(GOOD_DE)]), "PRV-")
    got = pairs(found)
    assert not [f for f in found if f.check_id == "PRV-LEG-001"]
    assert ("PRV-CMP-001", S.INFO) in got and ("PRV-CMP-001", S.WARNING) not in got


def test_hreflang_invalid_code_and_missing_return_link():
    first = ('<html lang="de"><head><link rel="alternate" hreflang="de" href="https://example.com/">'
             '<link rel="alternate" hreflang="en" href="https://example.com/en/">'
             '<link rel="alternate" hreflang="xx_YY" href="https://example.com/zz/"></head></html>')
    second = '<html lang="en"><head></head></html>'
    snap = make_snap([page(first), page(second, url="https://example.com/en/", depth=2)])
    found, _ = findings(snap, "SEO-HRF-")
    assert any(f.severity == S.WARNING and "language code" in f.msg_en for f in found)
    assert any(f.severity == S.WARNING and "return link" in f.msg_en for f in found)


def test_multilingual_site_without_hreflang_gets_a_note():
    snap = make_snap([page('<html lang="de"></html>'), page('<html lang="en"></html>', url="https://example.com/en/")])
    found, _ = findings(snap, "SEO-HRF-")
    assert pairs(found) == {("SEO-HRF-001", S.NOTE)}


def test_open_graph_and_structured_data():
    found, _ = findings(make_snap([page("<!doctype html><html><head><title>x</title></head></html>")]), "SEO-")
    assert ("SEO-SOC-001", S.NOTE) in pairs(found) and ("SEO-STR-001", S.INFO) in pairs(found)
    found, _ = findings(make_snap([page(OG_FULL)]), "SEO-")
    assert not [f for f in found if f.check_id in ("SEO-SOC-001", "SEO-STR-001")]
    broken = '<html><head><script type="application/ld+json">{not json}</script></head></html>'
    found, _ = findings(make_snap([page(broken)]), "SEO-STR-")
    assert ("SEO-STR-001", S.WARNING) in pairs(found)
    no_context = '<html><head><script type="application/ld+json">{"@type":"Thing"}</script></head></html>'
    found, _ = findings(make_snap([page(no_context)]), "SEO-STR-")
    assert any("@context" in f.msg_en for f in found)


class FakeGK:
    cancel = None

    def __init__(self, responses, default=(404, "text/html", "")):
        self.responses, self.default, self.calls = responses, default, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        path = urlsplit(url).path
        self.calls.append(path)
        status, ctype, body = self.responses.get(path, self.default)
        return Response(url, status, {"content-type": ctype}, [], body.encode(), False, 1)


class FakeResolver:
    async def query(self, name, rtype):
        return []


SITEMAP = ('<?xml version="1.0" encoding="UTF-8"?><urlset>'
           "<url><loc>https://example.com/</loc></url>"
           "<url><loc>https://example.com/gone</loc></url>"
           "<url><loc>http://example.com/old</loc></url></urlset>")


async def test_sitemap_problems_are_found():
    snap = make_snap([page(), page(url="https://example.com/a", depth=2)])
    gk = FakeGK({"/sitemap.xml": (200, "application/xml", SITEMAP), "/gone": (404, "text/html", "")})
    snap.extra["sitemap"] = await collect_sitemap(gk, snap)
    assert gk.calls == ["/sitemap.xml", "/gone"]
    found, executed = findings(snap, "SEO-SMP-")
    got = pairs(found)
    assert ("SEO-SMP-001", S.ERROR) in got and ("SEO-SMP-001", S.WARNING) in got and ("SEO-SMP-001", S.INFO) in got
    assert any("missing from the sitemap" in f.msg_en for f in found)
    assert executed["SEO-SMP-001"] == "ran"


async def test_missing_sitemap_is_a_note_and_unreachable_is_skipped():
    snap = make_snap([page()])
    snap.extra["sitemap"] = await collect_sitemap(FakeGK({}), snap)
    found, _ = findings(snap, "SEO-SMP-")
    assert pairs(found) == {("SEO-SMP-001", S.NOTE)}
    snap.extra["sitemap"] = {"found": False, "reachable": False}
    _, executed = findings(snap, "SEO-SMP-")
    assert executed["SEO-SMP-001"] == "skipped:sitemap_unreachable"


async def test_soft404_detection():
    snap = make_snap([page()])
    snap.extra["soft404"] = await probe_soft404(FakeGK({}, default=(200, "text/html", "<html>ok</html>")), snap)
    found, _ = findings(snap, "SEO-SFT-")
    assert pairs(found) == {("SEO-SFT-001", S.WARNING)}
    gk = FakeGK({})
    snap.extra["soft404"] = await probe_soft404(gk, snap)
    found, _ = findings(snap, "SEO-SFT-")
    assert found == [] and len(gk.calls) == 1 and gk.calls[0].startswith("/claudios-check-")


def test_new_probe_checks_are_skipped_without_data():
    _, executed = findings(make_snap([page()]), "SEO-")
    assert executed["SEO-SMP-001"] == "skipped:no_sitemap_data"
    assert executed["SEO-SFT-001"] == "skipped:no_soft404_data"


async def test_probes_report_progress_for_each_step():
    snap = make_snap([page(HOME_DE)])
    seen = []
    await gather_probes(FakeGK({}), snap, FakeResolver(),
                        progress=lambda stage, cur, total: seen.append((stage, cur, total)))
    assert [s[0] for s in seen] == ["probe:dns", "probe:takeover", "probe:ads", "probe:sitemap",
                                    "probe:soft404", "probe:assets", "probe:tls", "probe:links"]
    assert seen[-1][1:] == (8, 8)
    assert "sitemap" in snap.extra and "soft404" in snap.extra and "assets" in snap.extra


def test_numbers_in_findings_are_grouped_by_language():
    assert group_digits("Seite 12345 von 99999.", "de") == "Seite 12.345 von 99.999."
    assert group_digits("Page 12345 of 1234567", "en") == "Page 12,345 of 1,234,567"
    assert group_digits("HTTP 404, 2024.example.com, pub-1234567, v1234, 0123456", "de") == \
        "HTTP 404, 2024.example.com, pub-1234567, v1234, 0123456"
    finding = F("SEO-SMP-001", S.INFO, "https://example.com/", "12345 Seiten", "12345 pages", "id 12345")
    assert finding.msg_de == "12.345 Seiten" and finding.msg_en == "12,345 pages"
    assert finding.evidence == "id 12345"