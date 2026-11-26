"""Deinstallation aus dem Programm: was entfernt wird, was bei Fehlern gemeldet wird, wann der Deinstaller startet."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from claudios.ui import uninstall

_APP = QApplication.instance() or QApplication([])


def test_uninstaller_is_only_found_in_the_installed_program(tmp_path):
    exe = tmp_path / "CLAUDIOS.exe"
    assert uninstall.uninstaller_path(exe, frozen=False) is None  # aus dem Quelltext gestartet
    assert uninstall.uninstaller_path(exe, frozen=True) is None  # installiert, aber ohne unins000.exe
    (tmp_path / "unins000.exe").write_bytes(b"")
    assert uninstall.uninstaller_path(exe, frozen=True) == tmp_path / "unins000.exe"
    assert uninstall.uninstaller_path(exe, frozen=False) is None


@pytest.fixture
def parts(monkeypatch):
    """Attrappen für Komponenten, Verlauf und API-Schlüssel; jede Liste zeichnet auf, was entfernt wurde."""
    state = {"removed": [], "history": 0, "keys": [], "fail_history": False, "fail_keys": set(), "errors": {}}
    monkeypatch.setattr(uninstall.manager, "uninstall_items", lambda: [SimpleNamespace(key="a"), SimpleNamespace(key="b")])

    def remove(keys):
        state["removed"] += keys
        return {key: state["errors"].get(key) for key in keys}

    def delete_all():
        if state["fail_history"]:
            raise OSError("gesperrt")
        state["history"] += 1

    def delete_key(service):
        if service in state["fail_keys"]:
            raise OSError("gesperrt")
        state["keys"].append(service)

    monkeypatch.setattr(uninstall.manager, "uninstall", remove)
    monkeypatch.setattr(uninstall.history, "delete_all", delete_all)
    monkeypatch.setattr(uninstall.apikeys, "KNOWN", ("psi", "sb"))
    monkeypatch.setattr(uninstall.apikeys, "delete", delete_key)
    return state


def test_removal_clears_components_history_and_api_keys(parts):
    assert uninstall.perform_removal() == []
    assert parts["removed"] == ["a", "b"] and parts["history"] == 1 and parts["keys"] == ["psi", "sb"]


def test_removal_names_every_part_that_could_not_be_removed(parts):
    parts["errors"] = {"b": "PermissionError"}
    parts["fail_history"] = True
    parts["fail_keys"] = {"sb"}
    assert uninstall.perform_removal() == ["b", "history", "apikey:sb"]
    assert parts["keys"] == ["psi"]  # ein Fehler bricht die übrigen Schritte nicht ab


def test_removal_continues_when_the_component_list_cannot_be_read(parts, monkeypatch):
    def broken():
        raise RuntimeError("Sperrdatei defekt")

    monkeypatch.setattr(uninstall.manager, "uninstall_items", broken)
    assert uninstall.perform_removal() == ["components"]
    assert parts["removed"] == [] and parts["history"] == 1 and parts["keys"] == ["psi", "sb"]


@pytest.fixture
def flow(monkeypatch):
    state = {"answer": QMessageBox.StandardButton.Yes, "warnings": [], "infos": [], "started": [], "quit": 0,
             "closed": 0, "removed": 0, "failed": [], "installer": None, "stopped": []}

    def warning(_parent, _title, text, *_rest):
        state["warnings"].append(text)
        return state["answer"]

    monkeypatch.setattr(uninstall.QMessageBox, "warning", staticmethod(warning))
    monkeypatch.setattr(uninstall.QMessageBox, "information",
                        staticmethod(lambda _p, _t, text: state["infos"].append(text)))
    monkeypatch.setattr(uninstall.QProcess, "startDetached", staticmethod(lambda path, args: state["started"].append(
        (path, args))))
    monkeypatch.setattr(uninstall.QApplication, "quit", staticmethod(lambda: state.__setitem__("quit", state["quit"] + 1)))
    monkeypatch.setattr(uninstall, "_close_logging", lambda: state.__setitem__("closed", state["closed"] + 1))

    def removal():
        state["removed"] += 1
        return state["failed"]

    monkeypatch.setattr(uninstall, "perform_removal", removal)
    monkeypatch.setattr(uninstall, "uninstaller_path", lambda: state["installer"])
    return state


def _window(flow):
    page = SimpleNamespace(shutdown=lambda: flow["stopped"].append("scan"))
    return SimpleNamespace(pages=[page, SimpleNamespace()])  # Seiten ohne shutdown werden übergangen


def test_declining_the_confirmation_changes_nothing(flow):
    flow["answer"] = QMessageBox.StandardButton.No
    uninstall.run_uninstall(_window(flow))
    assert flow["removed"] == 0 and flow["closed"] == 0 and flow["stopped"] == [] and flow["quit"] == 0


def test_without_an_uninstaller_the_user_is_told_to_finish_by_hand(flow):
    uninstall.run_uninstall(_window(flow))
    assert flow["stopped"] == ["scan"] and flow["closed"] == 1 and flow["removed"] == 1
    assert len(flow["infos"]) == 1 and flow["started"] == [] and flow["quit"] == 0


def test_the_uninstaller_starts_detached_and_the_program_quits(flow, tmp_path):
    flow["installer"] = tmp_path / "unins000.exe"
    uninstall.run_uninstall(_window(flow))
    assert flow["started"] == [(str(tmp_path / "unins000.exe"), [])] and flow["quit"] == 1 and flow["infos"] == []


def test_parts_that_failed_are_listed_before_the_uninstaller_starts(flow, tmp_path):
    flow["failed"] = ["history", "apikey:sb"]
    flow["installer"] = tmp_path / "unins000.exe"
    uninstall.run_uninstall(_window(flow))
    assert len(flow["warnings"]) == 2 and "history, apikey:sb" in flow["warnings"][1]
    assert flow["quit"] == 1
