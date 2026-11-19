import time

import pytest

from claudios.core import audit_anchor
from claudios.core.audit_anchor import Anchor
from claudios.core.audit_log import AuditLog
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.limits import LIMITS
from claudios.core.quota import check_quota
from claudios.gsc import credstore
from claudios.gsc.credstore import MemoryStore


def make(tmp_path, store=None):
    store = MemoryStore() if store is None else store
    return AuditLog(tmp_path / "audit.jsonl", anchor=Anchor(store)), store


def fill(log, times=3):
    for _ in range(times):
        log.append("scan_start", domain="example.com", level=1)


def test_normal_use_passes_and_the_anchor_follows_the_log(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    log.guard()
    assert log.anchor.load() == (3, log.records()[-1]["hash"])


def test_deleting_the_log_blocks_for_24_hours(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    log.path.unlink()
    with pytest.raises(ClaudiosError) as error:
        log.guard()
    assert error.value.code == E.AUDIT_TAMPERED
    assert log.records()[0]["event"] == "tamper" and log.records()[0]["data"]["reason"] == "shorter"
    with pytest.raises(ClaudiosError):
        log.guard()  # die Sperre bleibt
    log.guard(now=time.time() + LIMITS.audit_tamper_lock_seconds + 10)  # danach ist wieder alles frei


def test_a_shortened_log_is_set_aside(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    lines = log.path.read_text("utf-8").splitlines()
    log.path.write_text("\n".join(lines[:2]) + "\n", "utf-8")
    with pytest.raises(ClaudiosError) as error:
        log.guard()
    assert error.value.code == E.AUDIT_TAMPERED
    assert (tmp_path / "audit.jsonl.tampered").is_file()


def test_an_edited_record_breaks_the_chain(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    log.path.write_text(log.path.read_text("utf-8").replace('"scan_start"', '"scan_stop"', 1), "utf-8")
    with pytest.raises(ClaudiosError):
        log.guard()
    assert log.records()[0]["data"]["reason"] == "chain"


def test_an_unreadable_log_counts_as_changed(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    log.path.write_text("das ist kein json\n", "utf-8")
    with pytest.raises(ClaudiosError):
        log.guard()


def test_a_new_entry_after_deleting_does_not_erase_the_evidence(tmp_path):
    log, _store = make(tmp_path)
    fill(log)
    log.path.unlink()
    log.append("scan_start", domain="example.com", level=1)
    assert log.anchor.load()[0] == 3  # der Kontrollwert wächst nur
    with pytest.raises(ClaudiosError):
        log.guard()


def test_a_missing_anchor_with_an_intact_log_is_adopted(tmp_path):
    plain = AuditLog(tmp_path / "audit.jsonl")  # wie nach dem Update von 6f-1: Protokoll ohne Kontrollwert
    fill(plain)
    log, _store = make(tmp_path)
    log.guard()
    assert log.anchor.load()[0] == 3


def test_a_fresh_start_without_log_and_anchor_is_fine(tmp_path):
    log, _store = make(tmp_path)
    log.guard()
    assert log.records() == []


def test_an_entry_missing_in_the_anchor_after_a_crash_is_accepted(tmp_path):
    log, store = make(tmp_path)
    fill(log, 2)
    AuditLog(tmp_path / "audit.jsonl").append("scan_start", domain="example.com", level=1)  # ohne Kontrollwert
    log.guard()
    assert log.anchor.load()[0] == 3
    assert store.read(audit_anchor.NAME)


def test_without_an_anchor_nothing_changes(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    fill(log)
    log.path.unlink()
    log.guard()


def test_check_quota_refuses_scans_after_tampering(tmp_path):
    log, _store = make(tmp_path)
    fill(log, 1)
    log.path.unlink()
    with pytest.raises(ClaudiosError) as error:
        check_quota(log, "example.com", 1, now=time.time() + 7200)
    assert error.value.code == E.AUDIT_TAMPERED


def test_default_anchor_needs_a_persistent_store(monkeypatch):
    monkeypatch.setattr(credstore, "get_store", lambda: MemoryStore(persistent=False))
    assert audit_anchor.default_anchor() is None
    monkeypatch.setattr(credstore, "get_store", lambda: MemoryStore(persistent=True))
    assert isinstance(audit_anchor.default_anchor(), Anchor)
