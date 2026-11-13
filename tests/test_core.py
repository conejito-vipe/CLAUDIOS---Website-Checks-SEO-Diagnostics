import time

import pytest

from claudios.checks import load_all
from claudios.core.audit_log import AuditLog
from claudios.core.errors import ClaudiosError, ErrorCode, catalog, describe
from claudios.core.guard import ip_allowed, normalize_input
from claudios.core.limits import LIMITS
from claudios.core.numfmt import format_bytes, format_number
from claudios.core.quota import check_quota
from claudios.core.redact import redact_text, redact_url
from claudios.core.registry import validate_registry
from claudios.core.snapshot import parse_set_cookie


def test_number_format_de_en():
    assert format_number(1234567.891, "de", 1) == "1.234.567,9"
    assert format_number(1234567.891, "en", 1) == "1,234,567.9"
    assert format_number(-1500, "de") == "-1.500"
    assert format_number(0, "en") == "0"
    assert format_bytes(1536, "de") == "1,5 KB" and format_bytes(1536, "en") == "1.5 KB"


def test_every_error_code_has_catalog_entry_in_both_languages():
    for code in ErrorCode:
        for lang in ("de", "en"):
            entry = catalog()[code.value][lang]
            assert len(entry) == 3 and all(x.strip() for x in entry)
    assert describe("CLA-XXX-999", "de")["code"] == ErrorCode.INTERNAL.value


def test_limits_are_fixed():
    assert LIMITS.max_depth == 6
    assert LIMITS.pages_for(1) == 25 and LIMITS.pages_for(2) == 100 and LIMITS.pages_for(2, "quick") == 5
    with pytest.raises(Exception):
        LIMITS.max_depth = 99  # frozen dataclass


@pytest.mark.parametrize("raw,code", [
    ("", ErrorCode.INPUT_EMPTY), ("http://example.com", ErrorCode.INPUT_NOT_HTTPS),
    ("https://user:pw@example.com", ErrorCode.INPUT_CREDENTIALS), ("127.0.0.1", ErrorCode.TARGET_PRIVATE),
    ("https://example.com:8443", ErrorCode.INPUT_INVALID), ("8.8.8.8", ErrorCode.INPUT_INVALID),
    ("intranet", ErrorCode.INPUT_INVALID), ("exa mple.com", ErrorCode.INPUT_INVALID)])
def test_guard_rejects(raw, code):
    with pytest.raises(ClaudiosError) as e:
        normalize_input(raw)
    assert e.value.code == code


def test_guard_accepts_and_normalizes():
    t = normalize_input("Example.com/path?x=1#frag")
    assert t.url == "https://example.com/path" and t.registrable == "example.com"
    assert normalize_input("http://localhost:8000", allow_localhost=True).loopback


@pytest.mark.parametrize("ip,ok", [("10.0.0.1", False), ("169.254.169.254", False), ("192.168.1.1", False),
                                   ("::ffff:127.0.0.1", False), ("127.0.0.1", False), ("93.184.216.34", True)])
def test_ssrf_ip_rules(ip, ok):
    assert ip_allowed(ip) is ok


def test_redaction():
    assert "hunter2hunter2" not in redact_text('password="hunter2hunter2"')
    assert "AKIAABCDEFGHIJKLMNOP" not in redact_text("key AKIAABCDEFGHIJKLMNOP")
    assert "[email]" in redact_text("mail: a.b@example.com")
    u = redact_url("https://user:pw@example.com/p?token=abc123&q=1#f")
    assert "abc123" not in u and "@" not in u and "q=1" in u and "#" not in u


def test_cookie_value_is_never_stored():
    c = parse_set_cookie("sid=SUPERSECRETVALUE; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=86400")
    assert c.name == "sid" and c.secure and c.httponly and c.samesite == "Lax"
    assert "SUPERSECRETVALUE" not in repr(c)
    assert c.lifetime_days == pytest.approx(1.0)


def test_audit_log_hash_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("scan_start", domain="example.com", level=1)
    log.append("scan_end", domain="example.com", status="complete")
    assert log.verify()
    log.path.write_text(log.path.read_text("utf-8").replace("example.com", "evil.com", 1), "utf-8")
    assert not log.verify()


def test_quota_cooldown_and_domain_limit(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    check_quota(log, "example.com", 1)
    log.append("scan_start", domain="example.com", level=1)
    with pytest.raises(ClaudiosError) as e:
        check_quota(log, "example.com", 1)
    assert e.value.code == ErrorCode.LIMIT_COOLDOWN
    log.append("scan_start", domain="example.com", level=1)
    log.append("scan_start", domain="example.com", level=1)
    later = time.time() + 300  # Abkühlzeit vorbei, Tageslimit der Stufe 1 (3) erreicht
    with pytest.raises(ClaudiosError) as e:
        check_quota(log, "example.com", 1, now=later)
    assert e.value.code == ErrorCode.LIMIT_DOMAIN_DAY
    check_quota(log, "example.com", 2, now=later)  # verifizierte Stufe 2 ist davon ausgenommen
    check_quota(log, "other.org", 1, now=later)


def test_registry_is_valid_and_has_why_in_both_languages():
    load_all()
    assert validate_registry() == []
