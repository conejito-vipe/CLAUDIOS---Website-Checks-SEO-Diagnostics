"""Scan-Protokoll nach einem Abbruch: halb geschriebene Zeile und BOM lösen keine Sperre aus, Manipulation weiterhin."""
from __future__ import annotations

import os

import pytest

from claudios.core.audit_anchor import Anchor
from claudios.core.audit_log import AuditLog
from claudios.core.errors import ClaudiosError


class MemStore:
    persistent = True

    def __init__(self):
        self.data = {}

    def read(self, name):
        return self.data.get(name)

    def write(self, name, value):
        self.data[name] = value


def make(tmp_path, entries=3):
    log = AuditLog(tmp_path / "audit.jsonl", anchor=Anchor(MemStore()))
    for _ in range(entries):
        log.append("scan_start", domain="a.example")
    return log


def test_torn_last_line_is_dropped_without_lock(tmp_path):
    log = make(tmp_path)
    with log.path.open("a", encoding="utf-8") as fh:
        fh.write('{"t": 1.0, "event": "scan_en')
    assert len(log.records()) == 3 and log.verify()
    log.guard()
    assert log.count("tamper", 10**9) == 0
    assert not log.path.with_name("audit.jsonl.tampered").exists()
    log.append("scan_end", domain="a.example")
    assert len(log.records()) == 4 and log.verify()
    assert log.path.read_bytes().count(b"\n") == 4


def test_bom_is_tolerated(tmp_path):
    log = make(tmp_path, 2)
    log.path.write_bytes(b"\xef\xbb\xbf" + log.path.read_bytes())
    assert len(log.records()) == 2 and log.verify()
    log.guard()
    assert log.count("tamper", 10**9) == 0


def test_garbage_with_line_end_is_still_unreadable(tmp_path):
    log = make(tmp_path, 2)
    with log.path.open("a", encoding="utf-8") as fh:
        fh.write("not json\n")
    with pytest.raises(ValueError):
        log.records()
    with pytest.raises(ClaudiosError):
        log.guard()


def test_removed_entries_are_still_detected(tmp_path):
    log = make(tmp_path, 3)
    lines = log.path.read_text("utf-8").splitlines()
    log.path.write_text("\n".join(lines[:2]) + "\n", "utf-8")
    with pytest.raises(ClaudiosError):
        log.guard()


def test_append_syncs_the_file(tmp_path, monkeypatch):
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), real(fd))[1])
    AuditLog(tmp_path / "a.jsonl").append("x", domain="d")
    assert calls
