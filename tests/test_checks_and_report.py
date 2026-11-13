import json
import zipfile
from contextlib import contextmanager
from hashlib import sha256

from claudios.checks import load_all
from claudios.core.engine import ScanResult, run_checks
from claudios.core.errors import ErrorCode, describe
from claudios.core.findings import Finding, Severity as S
from claudios.core.guard import normalize_input
from claudios.core.registry import REGISTRY, check
from claudios.core.scoring import compute_scores
from claudios.core.snapshot import Page, Snapshot, parse_set_cookie
from claudios.report.report import PROMPT, build_report, build_zip, render_html

BAD_HTML = """<html><head></head><body><img src="a.png">
<a href="https://x.example" target="_blank">x</a>
<iframe src="https://evil.example/f"></iframe>
<script>var k = "AKIAABCDEFGHIJKLMNOP";</script>
<script src="http://cdn.example/x.js"></script></body></html>"""

GOOD_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>A good page title</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="This is a sample description that is long enough to pass the length check.">
<link rel="canonical" href="https://example.com/"></head><body><main><h1>Hello</h1></main></body></html>"""

GOOD_HEADERS = {"content-security-policy": "default-src 'self'; frame-ancestors 'self'",
                "strict-transport-security": "max-age=31536000; includeSubDomains",
                "x-content-type-options": "nosniff", "referrer-policy": "strict-origin-when-cross-origin"}


def make_snap(html, headers=None, cookies=None):
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, headers=headers or {}, html=html,
                           content_type="text/html; charset=utf-8", cookies=cookies or []))
    snap.status = "complete"
    return snap


@contextmanager
def fake_check(cid, **kw):
    called = []

    @check(cid, title="T ## T", why="w ## w", method="m ## m", logic="l ## l", fix="f ## f",
           refs=["https://example.com/"], **kw)
    def _fn(snap):
        called.append(1)
        return []
    try:
        yield called
    finally:
        REGISTRY.pop(cid)


def test_bad_page_triggers_expected_checks():
    snap = make_snap(BAD_HTML, cookies=[parse_set_cookie("sid=abc; Path=/")])
    findings, executed = run_checks(snap, 1, "standard")
    expected = {"HTM-STR-001", "HTM-IMG-001", "SEC-HDR-001", "SEC-HDR-002", "SEC-HDR-004", "SEC-HTM-001",
                "SEC-HTM-002", "SEC-SEC-001", "SEC-NET-001", "SEC-COK-001", "SEO-MET-001"}
    assert expected <= {f.check_id for f in findings}
    assert all("AKIAABCDEFGHIJKLMNOP" not in f.evidence for f in findings)  # Geheimnis nur maskiert
    assert executed["HTM-STR-001"] == "ran"


def test_good_page_has_no_warnings_or_worse():
    findings, _ = run_checks(make_snap(GOOD_HTML, GOOD_HEADERS), 1, "standard")
    assert [f for f in findings if f.severity >= S.WARNING] == []


def test_active_checks_never_run_without_level2():
    with fake_check("TST-ACT-001", kind="active") as called:
        _, ex1 = run_checks(make_snap(GOOD_HTML), 1, "standard")
        assert ex1["TST-ACT-001"] == "skipped:level2_required" and called == []
        _, ex2 = run_checks(make_snap(GOOD_HTML), 2, "standard")
        assert ex2["TST-ACT-001"] == "ran" and called == [1]


def test_missing_component_is_not_reported_as_passed():
    with fake_check("TST-CMP-001", needs=("java",)) as called:
        _, ex = run_checks(make_snap(GOOD_HTML), 1, "standard", components=lambda n: False)
        assert ex["TST-CMP-001"] == "skipped:component_missing:java" and called == []


def test_aborted_scan_reports_reason_and_skips_everything_else():
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.status = "aborted"
    snap.abort = {"code": ErrorCode.TLS_CERT.value,
                  "de": describe(ErrorCode.TLS_CERT, "de", host="example.com", reason="expired"),
                  "en": describe(ErrorCode.TLS_CERT, "en", host="example.com", reason="expired")}
    findings, executed = run_checks(snap, 1, "standard")
    assert [f.severity for f in findings] == [S.CRITICAL]
    assert "expired" in findings[0].msg_en
    assert executed["SYS-ABT-001"] == "ran"
    assert all(v.startswith("skipped") for k, v in executed.items() if k != "SYS-ABT-001")


def test_scoring_ignores_checks_that_did_not_run():
    load_all()
    f = [Finding("SEC-HDR-002", S.WARNING, "https://example.com/", "d", "e")]
    s = compute_scores(f, {"SEC-HDR-002": "ran", "SEC-HDR-003": "ran", "SEO-MET-001": "skipped:x"})
    assert s["categories"] == {"SEC": 97} and s["overall"] == 97


def _result(findings_extra=()):
    snap = make_snap(BAD_HTML)
    findings, executed = run_checks(snap, 1, "standard")
    findings = findings + list(findings_extra)
    return ScanResult(snap, findings, executed, compute_scores(findings, executed),
                      requests=1, bytes_total=len(BAD_HTML))


def test_html_report_escapes_untrusted_content():
    evil = Finding("HTM-IMG-001", S.WARNING, "https://example.com/", "<b>x</b>", "<b>x</b>", "<script>alert(1)</script>")
    page = render_html(build_report(_result([evil]), "en"), "en")
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "Content-Security-Policy" in page


def test_zip_contains_no_decoy_secrets_and_valid_manifest(tmp_path):
    decoys = Finding("HTM-IMG-001", S.WARNING, "https://example.com/?token=DECOYTOKEN456",
                     "Test", "Test", "password=DECOYPASS123 -----BEGIN PRIVATE KEY-----abcdef")
    out = build_zip(_result([decoys]), tmp_path / "r.zip", "de")
    with zipfile.ZipFile(out) as z:
        texts = {n: z.read(n).decode("utf-8") for n in z.namelist()}
    assert {"prompt.md", "summary.md", "report.json", "report.html", "manifest.json"} == set(texts)
    blob = "\n".join(texts.values())
    for decoy in ("DECOYTOKEN456", "DECOYPASS123", "BEGIN PRIVATE KEY"):
        assert decoy not in blob
    manifest = json.loads(texts["manifest.json"])
    for name, info in manifest["files"].items():
        assert sha256(texts[name].encode()).hexdigest() == info["sha256"]
    assert isinstance(json.loads(texts["report.json"])["scan"]["pages_checked"], int)  # JSON: echte Zahlen


def test_prompt_mentions_number_format_per_language():
    assert "Tausendertrenner" in PROMPT["de"] and "thousands separator" in PROMPT["en"]
