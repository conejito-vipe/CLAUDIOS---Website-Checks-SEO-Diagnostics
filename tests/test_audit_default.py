from importlib.util import find_spec
from pathlib import Path

from claudios.core import audit_log
from claudios.core.audit_anchor import Anchor
from claudios.core.audit_log import AuditLog, use_default_anchor
from claudios.gsc.credstore import MemoryStore


def test_without_the_switch_a_log_has_no_anchor(tmp_path):
    assert AuditLog(tmp_path / "audit.jsonl").anchor is None


def test_the_switch_gives_new_logs_an_anchor(tmp_path, monkeypatch):
    monkeypatch.setitem(audit_log._DEFAULT, "factory", None)  # wird nach dem Test zurückgesetzt
    store = MemoryStore()
    use_default_anchor(lambda: Anchor(store))
    log = AuditLog(tmp_path / "audit.jsonl")
    assert isinstance(log.anchor, Anchor)
    log.append("scan_start", domain="example.com", level=1)
    assert log.anchor.load()[0] == 1


def test_an_explicit_anchor_wins_over_the_default(tmp_path, monkeypatch):
    monkeypatch.setitem(audit_log._DEFAULT, "factory", None)
    use_default_anchor(lambda: Anchor(MemoryStore()))
    own = Anchor(MemoryStore())
    assert AuditLog(tmp_path / "audit.jsonl", anchor=own).anchor is own


def test_a_factory_without_a_persistent_store_means_no_anchor(tmp_path, monkeypatch):
    monkeypatch.setitem(audit_log._DEFAULT, "factory", None)
    use_default_anchor(lambda: None)  # so verhält sich default_anchor ohne dauerhaften Speicher
    assert AuditLog(tmp_path / "audit.jsonl").anchor is None


def test_the_program_switches_the_anchor_on():
    text = Path(find_spec("claudios.app").origin).read_text("utf-8")
    assert "use_default_anchor(default_anchor)" in text
