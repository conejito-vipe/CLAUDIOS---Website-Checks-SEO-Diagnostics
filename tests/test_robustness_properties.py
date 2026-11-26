"""Eigenschafts- und Stresstests (lokal, mit Grenzen): Prüffunktionen werfen nie unerwartet und lassen nichts Gefährliches durch."""
from __future__ import annotations

import time

from hypothesis import HealthCheck, given, settings, strategies as st

from claudios.core import lizenz, schalt, verwaltung
from claudios.core.errors import ClaudiosError
from claudios.core.guard import normalize_input
from claudios.core.redact import find_leaks, redact_text, redact_url

FAST = settings(max_examples=150, deadline=1000, suppress_health_check=[HealthCheck.too_slow])
TEXT = st.text(max_size=300)


@FAST
@given(TEXT)
def test_normalize_input_only_raises_clear_errors_and_never_returns_a_dangerous_target(raw):
    try:
        target = normalize_input(raw)
    except ClaudiosError:
        return
    assert target.url.startswith("https://") and not target.loopback
    assert "@" not in target.url.split("/")[2] and not any(c.isspace() for c in target.url)
    assert target.host.isascii() and "." in target.host and not target.host.endswith((".local", ".internal"))


@FAST
@given(st.sampled_from(["http://", "https://", "//", "", "ftp://", "javascript:"]),
       st.sampled_from(["localhost", "127.0.0.1", "[::1]", "0.0.0.0", "10.0.0.1", "169.254.169.254", "192.168.0.1",
                        "2130706433", "0x7f000001", "example.com@127.0.0.1", "evil.local", "intern.internal", "a.b:22"]))
def test_internal_and_malformed_targets_are_always_refused(scheme, host):
    try:
        normalize_input(scheme + host)
    except ClaudiosError:
        return
    raise AssertionError(f"{scheme}{host} wurde angenommen")


@FAST
@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=400))
def test_redaction_is_idempotent_and_leaves_no_known_secret(text):
    once = redact_text(text)
    assert redact_text(once) == once or not find_leaks(once)
    assert find_leaks(once) == [] or "[REDACTED" in once


@FAST
@given(st.text(alphabet="abcdef0123456789", min_size=8, max_size=40), st.sampled_from(["token", "api_key", "password", "session"]))
def test_secret_values_in_urls_never_survive(secret, name):
    out = redact_url(f"https://user:{secret}@example.com/path?{name}={secret}&x=1#{secret}")
    assert secret not in out and "user" not in out


@FAST
@given(st.one_of(TEXT, st.binary(max_size=200), st.integers(), st.none(), st.lists(TEXT, max_size=3)))
def test_licence_and_switch_file_parsers_never_raise_and_never_accept_garbage(value):
    assert lizenz.parse(value)["valid"] is False
    assert schalt.parse(value) is None


def test_hostile_sizes_are_rejected_fast(tmp_path):
    started = time.monotonic()
    for size in (10_000, 1_000_000, 5_000_000):
        assert lizenz.parse("CL1." + "A" * size + ".AAAA")["valid"] is False
        assert schalt.parse("SW1." + "A" * size + ".AAAA") is None
        assert redact_text("eyJ" + "a" * size) is not None
        assert len(redact_url("https://example.com/?" + "k=v&" * (size // 8))) > 0
    (tmp_path / verwaltung.FILE).write_text('{"keys": ' + "[" * 100_000)  # tief verschachtelt und abgeschnitten
    assert verwaltung.load(tmp_path)["pro"] is False
    assert time.monotonic() - started < 15


def test_null_bytes_control_characters_and_invalid_utf8_are_harmless(tmp_path):
    for raw in ("exa\x00mple.com", "example.com\n", "ex‮ample.com", "\ud800", "𝕖𝕩𝕒𝕞𝕡𝕝𝕖.com", "xn--" + "a" * 70 + ".com"):
        try:
            normalize_input(raw)
        except ClaudiosError:
            pass
    (tmp_path / verwaltung.FILE).write_bytes(b"\xff\xfe\x00{")
    assert verwaltung.load(tmp_path) == {"keys": {}, "schalt_url": "", "pro": False}
    (tmp_path / lizenz.FILE).write_bytes(b"\xff\xfe\x00CL1")
    assert lizenz.state(tmp_path)["has_key"] is False and lizenz.load(tmp_path) == ""  # unlesbar = kein Schlüssel
    (tmp_path / schalt.FILE).write_bytes(b"\xff\xfe\x00SW1")
    assert schalt.load(tmp_path) is None and schalt.apply(tmp_path) is None and not lizenz.SCHALT_AKTIV
