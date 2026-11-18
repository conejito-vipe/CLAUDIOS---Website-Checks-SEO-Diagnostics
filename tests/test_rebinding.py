from types import SimpleNamespace

import pytest

from claudios.core import probe_zap, proof
from claudios.core.audit_log import AuditLog
from claudios.core.engine import run_scan
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.guard import ip_allowed
from claudios.core.limits import LIMITS
from claudios.core.rebind import recheck


@pytest.fixture(autouse=True)
def clean_proofs():
    proof._issued.clear()
    yield
    proof._issued.clear()


class Resolver:
    def __init__(self, table=None, default=None):
        self.table, self.default, self.asked = table if table is not None else {}, default, []

    async def addresses(self, host):
        self.asked.append(host)
        answer = self.table.get(host, self.default)
        if answer is None:
            raise ClaudiosError(E.TARGET_NO_DNS, host=host)
        return answer


def site(resolver, hosts=("example.com",)):
    return SimpleNamespace(target=SimpleNamespace(host="example.com"), resolver=resolver, allow_localhost=False,
                           _ips={h: ["8.8.8.8"] for h in hosts},
                           same_site=lambda h: h == "example.com" or h.endswith(".example.com"))


def gatekeeper():
    """Eine Attrappe mit den drei Merkmalen eines echten Gatekeepers (die Prüfung selbst ist ersetzt)."""
    return SimpleNamespace(target=SimpleNamespace(host="example.com"), resolver=object(), same_site=lambda h: True)


@pytest.mark.parametrize("ip,ok", [
    ("8.8.8.8", True), ("::ffff:10.0.0.1", False),
    ("64:ff9b::808:808", True), ("64:ff9b::7f00:1", False), ("64:ff9b::a00:1", False),
    ("2002:808:808::", True), ("2002:7f00:1::", False), ("2002:a00:1::", False)])
def test_embedded_ipv4_decides_for_nat64_and_6to4(ip, ok):
    assert ip_allowed(ip) is ok


async def test_recheck_looks_at_the_target_first_and_only_at_the_same_site():
    resolver = Resolver(default=["8.8.8.8"])
    gk = site(resolver, ("www.example.com", "cdn.other.test", "example.com"))
    assert await recheck(gk) == 2
    assert resolver.asked == ["example.com", "www.example.com"]


async def test_recheck_raises_when_a_host_flips_to_a_private_address():
    resolver = Resolver({"example.com": ["8.8.8.8"], "www.example.com": ["10.0.0.5"]})
    with pytest.raises(ClaudiosError) as error:
        await recheck(site(resolver, ("www.example.com",)))
    assert error.value.code == E.TARGET_PRIVATE


async def test_recheck_ignores_a_dns_outage():
    resolver = Resolver({"example.com": ["8.8.8.8"]})  # www.example.com: keine Antwort
    assert await recheck(site(resolver, ("www.example.com",))) == 1


async def test_recheck_is_limited():
    resolver = Resolver(default=["8.8.8.8"])
    await recheck(site(resolver, tuple(f"h{i}.example.com" for i in range(30))))
    assert len(resolver.asked) == LIMITS.rebind_hosts_max


def _snap(loopback=False):
    return SimpleNamespace(target=SimpleNamespace(loopback=loopback))


async def test_zap_is_not_started_when_the_site_already_points_to_a_private_address(monkeypatch):
    calls = []

    async def flipped(gk):
        raise ClaudiosError(E.TARGET_PRIVATE, host="example.com")

    monkeypatch.setattr(probe_zap, "recheck", flipped)
    monkeypatch.setattr(probe_zap, "_run", lambda snap: calls.append(1) or {"skip": None})
    assert await probe_zap.collect(gatekeeper(), _snap(), None) == {"skip": "dns_changed"}
    assert calls == []


async def test_zap_results_are_dropped_when_the_site_flips_during_the_run(monkeypatch):
    seen = []

    async def second_time_private(gk):
        seen.append(1)
        if len(seen) > 1:
            raise ClaudiosError(E.TARGET_PRIVATE, host="example.com")
        return 1

    monkeypatch.setattr(probe_zap, "recheck", second_time_private)
    monkeypatch.setattr(probe_zap, "_run", lambda snap: {"skip": None, "alerts": [{"name": "x"}]})
    assert await probe_zap.collect(gatekeeper(), _snap(), None) == {"skip": "dns_changed"}


async def test_a_clean_zap_run_passes_through_and_localhost_skips_the_check(monkeypatch):
    result = {"skip": None, "alerts": []}

    async def fine(gk):
        return 1

    async def never(gk):
        raise AssertionError("localhost braucht keine Prüfung")

    monkeypatch.setattr(probe_zap, "_run", lambda snap: result)
    monkeypatch.setattr(probe_zap, "recheck", fine)
    assert await probe_zap.collect(gatekeeper(), _snap(), None) is result
    monkeypatch.setattr(probe_zap, "recheck", never)
    assert await probe_zap.collect(gatekeeper(), _snap(loopback=True), None) is result


async def test_without_a_real_gatekeeper_there_is_nothing_to_recheck(monkeypatch):
    result = {"skip": None, "alerts": []}

    async def never(gk):
        raise AssertionError("ohne Gatekeeper gibt es nichts zu prüfen")

    monkeypatch.setattr(probe_zap, "_run", lambda snap: result)
    monkeypatch.setattr(probe_zap, "recheck", never)
    assert await probe_zap.collect(None, _snap(), None) is result
    assert await probe_zap.collect(SimpleNamespace(calls=[]), _snap(), None) is result


async def test_a_refused_scan_does_not_use_up_the_proof(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.append("scan_start", domain="example.com", level=2)  # Abkühlzeit läuft noch
    proof.issue("example.com", "sc-domain:example.com")
    with pytest.raises(ClaudiosError) as error:
        await run_scan("example.com", level=2, confirmed=True, audit=audit, lock_path=tmp_path / "scan.lock",
                       verified_property="sc-domain:example.com")
    assert error.value.code == E.LIMIT_COOLDOWN
    proof.require("example.com", "sc-domain:example.com")  # der Beleg ist noch da
