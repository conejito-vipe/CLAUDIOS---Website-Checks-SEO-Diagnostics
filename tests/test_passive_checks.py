from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from claudios.core import probe_passive
from claudios.core.engine import run_checks
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.net import Response
from claudios.core.snapshot import Page, Snapshot


def page(html="<html></html>", url="https://example.com/", depth=1, **kw):
    return Page(url=url, depth=depth, status=200, html=html, content_type="text/html; charset=utf-8", **kw)


def snap_of(*pages):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.extend(pages)
    snap.status = "complete"
    return snap


def run(snap, cid):
    found, executed = run_checks(snap, 1, "standard")
    return [f for f in found if f.check_id == cid], executed[cid]


def sevs(found):
    return sorted(f.severity for f in found)


def test_duplicate_ids():
    found, state = run(snap_of(page('<body><div id="a"></div><p id="a"></p><span id="b"></span></body>')), "HTM-IDS-001")
    assert state == "ran" and sevs(found) == [S.WARNING] and found[0].evidence == "a"
    assert run(snap_of(page('<body><div id="a"></div><p id="b"></p></body>')), "HTM-IDS-001")[0] == []


def test_headings():
    found, _ = run(snap_of(page("<body><h2>Intro</h2><h4>Deep</h4><h3></h3></body>")), "HTM-HDG-001")
    assert len(found) == 3 and {f.severity for f in found} == {S.NOTE, S.WARNING}
    assert run(snap_of(page("<body><h1>Title</h1><h2>Part</h2></body>")), "HTM-HDG-001")[0] == []


def test_landmarks():
    assert sevs(run(snap_of(page("<body><main>a</main><main>b</main></body>")), "HTM-LND-001")[0]) == [S.WARNING]
    assert sevs(run(snap_of(page("<body><p>x</p></body>")), "HTM-LND-001")[0]) == [S.NOTE]
    assert sevs(run(snap_of(page("<body><main></main><nav></nav><nav></nav></body>")), "HTM-LND-001")[0]) == [S.INFO]
    assert run(snap_of(page("<body><main></main></body>")), "HTM-LND-001")[0] == []


def test_forms():
    html = ('<form action="/x"><input type="text" name="q"><label for="e">Mail</label><input id="e" type="email">'
            '<label>Name <input type="text"></label><input type="hidden" name="t">'
            '<input type="text" aria-label="Zip"></form>')
    found, _ = run(snap_of(page(html)), "HTM-FRM-001")
    assert sevs(found) == [S.WARNING] and found[0].evidence == "q"
    insecure = '<form action="http:' + '//pay.example/x"></form>'
    assert sevs(run(snap_of(page(insecure)), "HTM-FRM-001")[0]) == [S.ERROR]
    by_get = '<form><input type="password" aria-label="pw"></form>'
    assert sevs(run(snap_of(page(by_get)), "HTM-FRM-001")[0]) == [S.WARNING]


def test_permissions_policy_and_isolation():
    assert sevs(run(snap_of(page()), "SEC-PPL-001")[0]) == [S.INFO]
    found, _ = run(snap_of(page(headers={"permissions-policy": "camera=*, microphone=()"})), "SEC-PPL-001")
    assert sevs(found) == [S.NOTE] and "camera" in found[0].msg_en
    assert sevs(run(snap_of(page()), "SEC-COI-001")[0]) == [S.INFO]
    assert sevs(run(snap_of(page(headers={"cross-origin-opener-policy": "bogus"})), "SEC-COI-001")[0]) == [S.NOTE]
    good = {"cross-origin-opener-policy": "same-origin", "cross-origin-embedder-policy": "require-corp",
            "cross-origin-resource-policy": "same-site"}
    assert run(snap_of(page(headers=good)), "SEC-COI-001")[0] == []
    only_coep = {"cross-origin-embedder-policy": "require-corp"}
    assert sevs(run(snap_of(page(headers=only_coep)), "SEC-COI-001")[0]) == [S.INFO]


def test_compression_and_caching():
    assert sevs(run(snap_of(page(size=5000)), "SEO-CMP-001")[0]) == [S.NOTE]
    assert sevs(run(snap_of(page(size=150_000)), "SEO-CMP-001")[0]) == [S.WARNING]
    assert run(snap_of(page(size=5000, headers={"content-encoding": "br"})), "SEO-CMP-001")[0] == []
    assert run(snap_of(page(size=500)), "SEO-CMP-001")[0] == []
    assert sevs(run(snap_of(page()), "SEO-CCH-001")[0]) == [S.NOTE]
    assert run(snap_of(page(headers={"etag": "x"})), "SEO-CCH-001")[0] == []
    assert sevs(run(snap_of(page(headers={"cache-control": "no-store"})), "SEO-CCH-001")[0]) == [S.INFO]


def test_thin_and_duplicate_content():
    few = "<body><p>Hello world</p></body>"
    assert sevs(run(snap_of(page(few)), "SEO-THN-001")[0]) == [S.NOTE]
    assert run(snap_of(page("<body><p>" + "word " * 200 + "</p></body>")), "SEO-THN-001")[0] == []
    assert sevs(run(snap_of(page("<body><p>" + "word " * 100 + "</p></body>")), "SEO-THN-001")[0]) == [S.INFO]
    same = "<body><p>" + "text " * 60 + "</p></body>"
    found, _ = run(snap_of(page(same, url="https://example.com/a"), page(same, url="https://example.com/b")),
                   "SEO-THN-001")
    assert sorted({f.severity for f in found}) == [S.INFO, S.NOTE] and len(found) == 2


def test_url_structure_and_click_depth():
    snap = snap_of(page(url="https://example.com/Alpha_Beta"), page(url="https://example.com/p?PHPSESSID=abc"),
                   page(url="https://example.com/a/b/c/d/e/f"), page(url="https://example.com/"))
    found, _ = run(snap, "SEO-URL-001")
    assert len(found) == 4 and S.WARNING in {f.severity for f in found}
    flat = snap_of(*(page(url=f"https://example.com/p{i}", depth=i) for i in (1, 2, 3, 4)))
    assert run(flat, "SEO-CLK-001")[0] == []
    deep = snap_of(*(page(url=f"https://example.com/p{i}", depth=i) for i in (1, 2, 5, 6)))
    assert sevs(run(deep, "SEO-CLK-001")[0]) == [S.INFO, S.NOTE]


def robots(text):
    snap = snap_of(page())
    snap.robots_txt = text
    return run(snap, "SEO-RBD-001")


def test_robots_in_detail():
    text = ("User-agent: *\nDisallow: /*.css$\nDisallow: /wp-includes/\nCrawl-delay: 5\nDissallow: /x\n"
            "Sitemap: /sitemap.xml\nNoindex: /y\n")
    found, state = robots(text)
    assert state == "ran" and len(found) == 5 and S.WARNING in {f.severity for f in found}
    assert sevs(robots("User-agent: Googlebot\nDisallow: /\n")[0]) == [S.WARNING]
    assert sevs(robots("Disallow: /x\nUser-agent: *\nDisallow: /y\n")[0]) == [S.NOTE]
    assert sevs(robots("User-agent: *\n" + "Disallow: /a\n" * 45000)[0]) == [S.WARNING]
    assert sevs(robots(None)[0]) == [S.INFO]


def passive_snap(**data):
    snap = snap_of(page())
    snap.extra["passive"] = data
    return snap


def txt(status=200, text="", ctype="text/plain", legacy=None, error=None):
    return {"path": "/.well-known/security.txt", "status": status, "error": error, "content_type": ctype,
            "text": text, "legacy": legacy}


def stamp(days):
    return (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_security_txt():
    good = f"Contact: mailto:security@example.com\nExpires: {stamp(100)}\n"
    assert run(passive_snap(security_txt=txt(text=good)), "SEC-TXT-001") == ([], "ran")
    assert sevs(run(passive_snap(security_txt=txt(text="Contact: mailto:a@example.com\n")), "SEC-TXT-001")[0]) == [S.WARNING]
    old = f"Contact: mailto:a@example.com\nExpires: {stamp(-5)}\n"
    assert sevs(run(passive_snap(security_txt=txt(text=old)), "SEC-TXT-001")[0]) == [S.WARNING]
    far = f"Contact: mailto:a@example.com\nExpires: {stamp(800)}\n"
    assert sevs(run(passive_snap(security_txt=txt(text=far)), "SEC-TXT-001")[0]) == [S.NOTE]
    assert sevs(run(passive_snap(security_txt=txt(status=404)), "SEC-TXT-001")[0]) == [S.INFO]
    legacy = {"status": 200, "error": None}
    assert sevs(run(passive_snap(security_txt=txt(status=404, legacy=legacy)), "SEC-TXT-001")[0]) == [S.NOTE]
    assert sevs(run(passive_snap(security_txt=txt(text="<html>", ctype="text/html")), "SEC-TXT-001")[0]) == [S.WARNING]
    assert run(passive_snap(security_txt=txt(error="CLA-NET-001")), "SEC-TXT-001")[1] == "skipped:security_txt_unreachable"


def test_favicon():
    def fav(declared, status, ctype="image/png", error=None):
        fetch = {"status": status, "error": error, "content_type": ctype, "text": ""}
        return {"skipped": False, "declared": declared, "inline": False, "external": False, "fetch": fetch}

    assert sevs(run(passive_snap(favicon=fav(False, 404, "text/html")), "SEO-FAV-001")[0]) == [S.NOTE]
    assert sevs(run(passive_snap(favicon=fav(False, 200, "image/x-icon")), "SEO-FAV-001")[0]) == [S.INFO]
    assert sevs(run(passive_snap(favicon=fav(True, 404)), "SEO-FAV-001")[0]) == [S.WARNING]
    assert run(passive_snap(favicon=fav(True, 200)), "SEO-FAV-001")[0] == []
    assert run(passive_snap(favicon=fav(True, None, error="CLA-NET-001")), "SEO-FAV-001")[1] == "skipped:favicon_unreachable"


def mta_snap(policy):
    snap = passive_snap(mta_sts=policy)
    snap.extra["dns"] = {"records": {"mta_sts": ['"v=STSv1; id=1"'], "mx": ["10 mail.example.com."]}}
    return snap


def policy(text, status=200):
    return {"path": "/.well-known/mta-sts.txt", "status": status, "error": None, "content_type": "text/plain",
            "text": text}


def test_mta_sts_file():
    good = "version: STSv1\nmode: enforce\nmx: mail.example.com\nmax_age: 604800\n"
    assert run(mta_snap(policy(good)), "DNS-MTF-001") == ([], "ran")
    assert sevs(run(mta_snap(policy("", status=404)), "DNS-MTF-001")[0]) == [S.WARNING]
    assert sevs(run(mta_snap(policy(good.replace("enforce", "testing"))), "DNS-MTF-001")[0]) == [S.NOTE]
    assert sevs(run(mta_snap(policy(good.replace("mail.example.com", "other.example.net"))), "DNS-MTF-001")[0]) == [S.WARNING]
    assert sevs(run(mta_snap(policy(good.replace("604800", "3600"))), "DNS-MTF-001")[0]) == [S.NOTE]
    wildcard = good.replace("mail.example.com", "*.example.com")
    assert run(mta_snap(policy(wildcard)), "DNS-MTF-001")[0] == []


def test_takeover_fingerprints_and_missing_data():
    hit = [{"host": "blog.example.com", "service": "GitHub Pages", "status": 404, "error": None, "matched": True}]
    assert sevs(run(passive_snap(takeover=hit), "TKO-FNG-001")[0]) == [S.WARNING]
    assert run(passive_snap(takeover=[]), "TKO-FNG-001") == ([], "ran")
    assert run(passive_snap(takeover=None), "TKO-FNG-001")[1] == "skipped:no_takeover_data"
    plain = snap_of(page())
    _, executed = run_checks(plain, 1, "standard")
    for cid in ("SEC-TXT-001", "SEO-FAV-001", "DNS-MTF-001", "TKO-FNG-001"):
        assert executed[cid] == "skipped:no_passive_data"


class FakeGK:
    cancel = None

    def __init__(self, responses):
        self.responses, self.calls = responses, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        assert method == "GET"
        parts = urlsplit(url)
        self.calls.append((parts.netloc, parts.path, follow))
        status, ctype, body = self.responses.get((parts.netloc, parts.path), (404, "text/html", b""))
        return Response(url, status, {"content-type": ctype}, [], body, False, 1)


async def test_the_probe_collects_the_extra_files():
    html = '<html><head><link rel="icon" href="/fav.png"></head><body></body></html>'
    snap = snap_of(page(html))
    snap.extra["dns"] = {"records": {"mta_sts": ['"v=STSv1; id=1"'], "mx": ["10 mail.example.com."]}}
    snap.extra["takeover"] = {"hosts": 1, "queries": 3, "limited": False, "records": [
        {"host": "blog.example.com", "chain": ["x.github.io"], "target": "x.github.io",
         "service": "GitHub Pages", "resolves": True}]}
    gk = FakeGK({
        ("example.com", "/.well-known/security.txt"): (200, "text/plain", b"Contact: mailto:a@example.com\n"),
        ("example.com", "/fav.png"): (200, "image/png", b"x"),
        ("mta-sts.example.com", "/.well-known/mta-sts.txt"): (200, "text/plain", b"version: STSv1\n"),
        ("blog.example.com", "/"): (404, "text/html", b"<html>There isn't a GitHub Pages site here.</html>"),
    })
    data = await probe_passive.collect(gk, snap, None)
    assert data["security_txt"]["status"] == 200 and data["favicon"]["fetch"]["status"] == 200
    assert data["mta_sts"]["status"] == 200 and data["takeover"][0]["matched"] is True
    assert len(gk.calls) == 4 and ("mta-sts.example.com", "/.well-known/mta-sts.txt", False) in gk.calls


async def test_the_probe_stays_small_without_dns_and_takeover_data():
    gk = FakeGK({})
    data = await probe_passive.collect(gk, snap_of(page()), None)
    assert data["mta_sts"] is None and data["takeover"] is None
    assert [call[1] for call in gk.calls] == ["/.well-known/security.txt", "/security.txt", "/favicon.ico"]
    assert probe_passive.MIN_LEVEL == 1
