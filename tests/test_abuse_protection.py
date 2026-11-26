import importlib
import pkgutil
import time

import pytest

from claudios import core as core_pkg
from claudios.checks import load_all
from claudios.core import proof
from claudios.core.audit_log import AuditLog
from claudios.core.engine import run_scan
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.quota import check_quota
from claudios.core.registry import REGISTRY

ACTIVE_CHECKS = {"EXP-PTH-001", "SEC-CMX-001", "GSC-IDX-001", "GSC-SMP-001", "TLS-ATK-001", "ZAP-PAS-001"}
LEVEL2_PROBES = {"paths", "zap", "cms"}


@pytest.fixture(autouse=True)
def clean_proofs():
    proof._issued.clear()
    yield
    proof._issued.clear()


@pytest.mark.parametrize("prop,host,ok", [
    ("sc-domain:example.com", "example.com", True), ("sc-domain:example.com", "shop.example.com", True),
    ("sc-domain:example.com", "notexample.com", False), ("https://www.other.test/", "www.other.test", True),
    ("https://www.other.test/", "other.test", False), ("https://sub.third.test/blog/", "sub.third.test", False),
    ("http" + "://plain.test/", "plain.test", False), ("sc-domain:", "example.com", False)])
def test_property_must_cover_the_whole_domain(prop, host, ok):
    assert proof.property_covers(prop, host) is ok


def test_proof_is_bound_to_host_and_property_expires_and_is_single_use():
    proof.issue("example.com", "sc-domain:example.com", now=1000.0)
    for host, prop in (("other.com", "sc-domain:example.com"), ("example.com", "sc-domain:other.test"),
                       ("example.com", None)):
        with pytest.raises(ClaudiosError) as error:
            proof.require(host, prop, now=1001.0)
        assert error.value.code == E.PERM_LEVEL2
    proof.require("example.com", "sc-domain:example.com", now=1001.0)  # der Beleg war nicht verbraucht
    with pytest.raises(ClaudiosError):
        proof.require("example.com", "sc-domain:example.com", now=1002.0)  # gilt nur einmal
    proof.issue("example.com", "sc-domain:example.com", now=1000.0)
    with pytest.raises(ClaudiosError):
        proof.require("example.com", "sc-domain:example.com", now=1000.0 + proof.TTL_SECONDS + 1)


async def test_a_level_2_scan_needs_a_fresh_proof_and_logs_nothing_without_it(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    for prop in (None, "sc-domain:example.com", "sc-domain:other.test"):
        with pytest.raises(ClaudiosError) as error:
            await run_scan("example.com", level=2, confirmed=True, audit=audit, lock_path=tmp_path / "scan.lock",
                           verified_property=prop)
        assert error.value.code == E.PERM_LEVEL2
    assert audit.records() == []


def test_level_2_has_a_daily_limit_per_domain(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for _ in range(LIMITS.scans_per_domain_day_level2):
        log.append("scan_start", domain="example.com", level=2)
    later = time.time() + 7200  # Abkühlzeit und Stundenfenster sind vorbei, das Tagesfenster nicht
    with pytest.raises(ClaudiosError) as error:
        check_quota(log, "example.com", 2, now=later)
    assert error.value.code == E.LIMIT_DOMAIN_DAY_L2
    check_quota(log, "other.org", 2, now=later)


@pytest.mark.parametrize("raw,code", [
    ("a_b.example.com", E.INPUT_INVALID), ("-bad.example.com", E.INPUT_INVALID),
    ("bad-.example.com", E.INPUT_INVALID), ("a" * 64 + ".com", E.INPUT_INVALID),
    ("ex%41mple.com", E.INPUT_INVALID), ("a..b.com", E.INPUT_INVALID), ("a." * 130 + "com", E.INPUT_INVALID),
    ("printer.local", E.TARGET_PRIVATE), ("x.internal", E.TARGET_PRIVATE), ("nas.lan", E.TARGET_PRIVATE),
    ("foo.localhost", E.TARGET_PRIVATE), ("router.home.arpa", E.TARGET_PRIVATE)])
def test_hostnames_with_odd_characters_or_local_suffixes_are_rejected(raw, code):
    with pytest.raises(ClaudiosError) as error:
        normalize_input(raw)
    assert error.value.code == code


def test_umlaut_domains_become_punycode_and_normal_names_still_pass():
    assert normalize_input("bücher.example").host == "xn--bcher-kva.example"
    assert normalize_input("Sub-1.Example.com").host == "sub-1.example.com"


def test_only_reviewed_checks_and_probes_may_be_active():
    load_all()
    active = {cid for cid, rc in REGISTRY.items() if rc.meta.kind == "active"}
    assert active == ACTIVE_CHECKS, f"aktive Prüfungen geändert: neu {active - ACTIVE_CHECKS}, weg {ACTIVE_CHECKS - active}"
    level2 = set()
    for info in pkgutil.iter_modules(core_pkg.__path__):
        if info.name.startswith("probe_"):
            module = importlib.import_module(f"claudios.core.{info.name}")
            if getattr(module, "MIN_LEVEL", 1) >= 2:
                level2.add(module.NAME)
    assert level2 == LEVEL2_PROBES
