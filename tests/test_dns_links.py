from urllib.parse import urlsplit

from claudios.core import engine as engine_module
from claudios.core.audit_log import AuditLog
from claudios.core.dnsprobe import collect_dns
from claudios.core.engine import run_checks, run_scan
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.linkprobe import check_external_links
from claudios.core.net import Response
from claudios.core.probes import gather_probes
from claudios.core.snapshot import Page, Snapshot

D = "example.com"
NS2 = ["ns1.example.net.", "ns2.example.org."]
GOOD = {
    (D, "MX"): ["10 mail.example.com."],
    (D, "NS"): NS2,
    (D, "TXT"): ['"v=spf1 include:_spf.example.net -all"', '"google-site-verification=abc"'],
    ("_spf.example.net", "TXT"): ['"v=spf1 ip4:192.0.2.0/24 -all"'],
    (f"_dmarc.{D}", "TXT"): ['"v=DMARC1; p=reject; rua=mailto:dmarc@example.com"'],
    (D, "CAA"): ['0 issue "letsencrypt.org"'],
    (D, "DS"): ["12345 13 2 ABCDEF"],
    (D, "AAAA"): ["2001:db8::1"],
    (f"_mta-sts.{D}", "TXT"): ['"v=STSv1; id=1"'],
    (f"_smtp._tls.{D}", "TXT"): ['"v=TLSRPTv1; rua=mailto:tls@example.com"'],
    (f"google._domainkey.{D}", "TXT"): ['"v=DKIM1; k=rsa; p=MIGfMA0GCSq"'],
}


class FakeResolver:
    def __init__(self, zone):
        self.zone = zone

    async def query(self, name, rtype):
        return list(self.zone.get((name, rtype), []))


class BrokenResolver:
    async def query(self, name, rtype):
        raise OSError("down")


def page(url="https://example.com/", depth=1, status=200, html="<html></html>", **kw):
    return Page(url=url, depth=depth, status=status, html=html, content_type="text/html", **kw)


def new_snap():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(page())
    return snap


async def dns_findings(zone, resolver=None):
    snap = new_snap()
    snap.extra["dns"] = await collect_dns(resolver or FakeResolver(zone), snap.target.host, snap.target.registrable)
    findings, executed = run_checks(snap, 1, "standard")
    return [f for f in findings if f.check_id.startswith("DNS-")], executed


def pairs(found):
    return {(f.check_id, f.severity) for f in found}


async def test_good_dns_has_no_findings_above_info():
    found, executed = await dns_findings(GOOD)
    assert [f for f in found if f.severity >= S.NOTE] == []
    assert all(v == "ran" for k, v in executed.items() if k.startswith("DNS-"))


async def test_bad_dns_reports_problems():
    bad = {(D, "MX"): ["10 mail.example.com."], (D, "NS"): ["ns1.example.net."], (D, "TXT"): ['"hello"']}
    found, _ = await dns_findings(bad)
    got = pairs(found)
    for expected in (("DNS-SPF-001", S.WARNING), ("DNS-DMA-001", S.WARNING), ("DNS-BAS-001", S.WARNING),
                     ("DNS-CAA-001", S.NOTE), ("DNS-SEC-001", S.NOTE), ("DNS-DKM-001", S.NOTE)):
        assert expected in got


async def test_spf_plus_all_and_too_many_lookups():
    base = {(D, "MX"): ["10 mail.example.com."], (D, "NS"): NS2}
    found, _ = await dns_findings({**base, (D, "TXT"): ['"v=spf1 +all"']})
    assert ("DNS-SPF-001", S.ERROR) in pairs(found)
    many = '"v=spf1 ' + "a " * 11 + '-all"'
    found, _ = await dns_findings({**base, (D, "TXT"): [many]})
    assert any("more than 10" in f.msg_en for f in found if f.check_id == "DNS-SPF-001")


async def test_domain_without_mail_gets_only_notes():
    zone = {(D, "MX"): ["0 ."], (D, "NS"): NS2, (D, "TXT"): []}
    found, _ = await dns_findings(zone)
    spf = [f for f in found if f.check_id == "DNS-SPF-001"]
    assert spf and spf[0].severity == S.NOTE
    assert not any(f.check_id == "DNS-DKM-001" for f in found)
    assert max(f.severity for f in found) <= S.NOTE


def test_dns_checks_are_skipped_without_data():
    _, executed = run_checks(new_snap(), 1, "standard")
    assert executed["DNS-SPF-001"] == "skipped:no_dns_data"
    assert executed["LNK-EXT-001"] == "skipped:no_link_data"


async def test_unreachable_dns_is_not_reported_as_passed():
    found, executed = await dns_findings({}, resolver=BrokenResolver())
    assert found == []
    assert executed["DNS-SPF-001"] == "skipped:dns_unreachable"


HOME = """<!doctype html><html lang="en"><head><title>Home page title</title></head><body>
<a href="#nope">jump</a> <a href="#ok">ok</a> <h2 id="ok">Section</h2>
<a href="mailto:not-an-address">mail</a> <a href="mailto:me@example.com">good</a> <a href="tel:abc">phone</a>
<a href="/x">click here</a> <a href="/y"></a> <a href="/z">A clear descriptive link</a></body></html>"""


def link_snap():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.extend([
        page(html=HOME, internal_links=["https://example.com/missing"]),
        page(url="https://example.com/missing", depth=2, status=404),
        page(url="https://example.com/c", depth=2, chain=["https://example.com/a", "https://example.com/b"]),
    ])
    return snap


def test_link_checks_find_the_planted_problems():
    findings, executed = run_checks(link_snap(), 1, "standard")
    got = pairs([f for f in findings if f.check_id.startswith("LNK-")])
    for expected in (("LNK-INT-001", S.ERROR), ("LNK-RED-001", S.NOTE), ("LNK-ANC-001", S.NOTE),
                     ("LNK-MAI-001", S.WARNING), ("LNK-MAI-001", S.NOTE),
                     ("LNK-TXT-001", S.WARNING), ("LNK-TXT-001", S.NOTE)):
        assert expected in got
    internal = [f for f in findings if f.check_id == "LNK-INT-001"]
    assert len(internal) == 1 and "example.com" in internal[0].evidence
    assert executed["LNK-INT-001"] == "ran"


class FakeGK:
    cancel = None

    def __init__(self, status_by_path):
        self.status_by_path, self.calls = status_by_path, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        self.calls.append((method, url))
        path = urlsplit(url).path
        status = self.status_by_path.get(path, 200)
        if path == "/nohead" and method == "HEAD":
            status = 405
        return Response(url, status, {}, [], b"", False, 1)


async def test_external_links_use_head_with_get_fallback():
    snap = link_snap()
    snap.pages[0].external_links = ["https://ext.example/ok", "https://ext.example/gone", "https://ext.example/nohead"]
    gk = FakeGK({"/gone": 404})
    data = await check_external_links(gk, snap)
    by_url = {r["url"]: r for r in data["results"]}
    assert by_url["https://ext.example/ok"]["status"] == 200
    assert by_url["https://ext.example/gone"]["status"] == 404
    assert by_url["https://ext.example/nohead"]["status"] == 200
    assert ("GET", "https://ext.example/nohead") in gk.calls
    snap.extra["links"] = data
    findings, _ = run_checks(snap, 1, "standard")
    ext = [f for f in findings if f.check_id == "LNK-EXT-001"]
    assert len(ext) == 1 and ext[0].severity == S.ERROR


async def test_external_link_limit_is_enforced():
    snap = link_snap()
    snap.pages[0].external_links = [f"https://ext.example/p{i}" for i in range(LIMITS.external_links_checked + 50)]
    data = await check_external_links(FakeGK({}), snap)
    assert data["checked"] == LIMITS.external_links_checked
    assert data["unique"] == LIMITS.external_links_checked + 50
    snap.extra["links"] = data
    findings, _ = run_checks(snap, 1, "standard")
    assert any(f.severity == S.INFO and "not checked" in f.msg_en for f in findings if f.check_id == "LNK-EXT-001")


async def test_probes_skipped_for_quick_profile_and_localhost():
    quick = link_snap()
    quick.profile = "quick"
    await gather_probes(FakeGK({}), quick, FakeResolver({}))
    assert quick.extra == {}
    local = link_snap()
    local.target = normalize_input("http://localhost:8000", allow_localhost=True)
    await gather_probes(FakeGK({}), local, FakeResolver({}))
    assert local.extra == {}


async def test_probes_fill_extra_for_standard_scan():
    snap = link_snap()
    snap.pages[0].external_links = ["https://ext.example/ok"]
    await gather_probes(FakeGK({}), snap, FakeResolver(GOOD))
    assert snap.extra["dns"]["records"]["mx"] == ["10 mail.example.com."]
    assert snap.extra["links"]["checked"] == 1


class ScanGK:
    """Ersetzt den Gatekeeper im Engine-Test: liefert eine winzige Website."""

    def __init__(self, target, *, resolver, allow_localhost=False, cancel=None):
        self.cancel, self.requests, self.bytes_total = cancel, 0, 0

    async def fetch(self, url, **kw):
        self.requests += 1
        if urlsplit(url).path == "/robots.txt":
            return Response(url, 404, {}, [], b"", False, 1)
        html = '<!doctype html><html lang="en"><head><title>t</title></head><body><a href="/">home</a></body></html>'
        return Response(url, 200, {"content-type": "text/html; charset=utf-8"}, [], html.encode(), False, 1)

    async def aclose(self):
        return None


async def test_run_scan_integrates_crawl_probes_and_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "Gatekeeper", ScanGK)
    audit = AuditLog(tmp_path / "audit.jsonl")
    result = await run_scan("example.com", level=1, confirmed=True, audit=audit,
                            lock_path=tmp_path / "scan.lock", resolver=FakeResolver(GOOD))
    assert result.snapshot.abort is None
    assert result.snapshot.status in ("complete", "limited")
    assert "dns" in result.snapshot.extra
    assert result.executed["DNS-SPF-001"] == "ran"
    assert audit.verify() and audit.last_time("scan_end") is not None
