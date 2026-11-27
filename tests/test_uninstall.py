"""Deinstallation aus dem Programm: was entfernt wird, was bei Fehlern gemeldet wird, wann der Deinstaller startet."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from claudios.ui import uninstall, uninstall_dialog

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

    def removal(selected=None):
        state["removed"] += 1
        state["got"] = selected
        return state["failed"]

    class FakeDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, _parent, _items):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted if state["answer"] == QMessageBox.StandardButton.Yes \
                else QDialog.DialogCode.Rejected

        def selected(self):
            return state["selected"]

    state["selected"] = {"cache", "program"}
    monkeypatch.setattr(uninstall_dialog, "UninstallDialog", FakeDialog)
    monkeypatch.setattr(uninstall, "plan", lambda: [])
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


def test_only_the_chosen_parts_are_removed_and_without_the_program_the_app_keeps_running(flow, tmp_path):
    flow["selected"] = {"cache", "logs"}
    flow["installer"] = tmp_path / "unins000.exe"
    uninstall.run_uninstall(_window(flow))
    assert flow["got"] == {"cache", "logs"} and flow["started"] == [] and flow["quit"] == 0


def test_parts_that_failed_are_listed_before_the_uninstaller_starts(flow, tmp_path):
    flow["failed"] = ["history", "apikey:sb"]
    flow["installer"] = tmp_path / "unins000.exe"
    uninstall.run_uninstall(_window(flow))
    assert len(flow["warnings"]) == 1 and "history, apikey:sb" in flow["warnings"][0]
    assert flow["quit"] == 1


def test_a_selection_limits_what_perform_removal_touches(parts):
    assert uninstall.perform_removal({"a", "history"}) == []
    assert parts["removed"] == ["a"] and parts["history"] == 1 and parts["keys"] == []
    parts["removed"].clear()
    assert uninstall.perform_removal({"keys"}) == []
    assert parts["removed"] == [] and parts["history"] == 1 and parts["keys"] == ["psi", "sb"]


def test_the_plan_lists_everything_and_keeps_personal_data_unticked(monkeypatch, tmp_path):
    items = [SimpleNamespace(key="tool:java", title="Java", size=10, default=True),
             SimpleNamespace(key="config", title="config", size=5, default=False)]
    monkeypatch.setattr(uninstall.manager, "uninstall_items", lambda: items)
    monkeypatch.setattr(uninstall.history, "count", lambda: 3)
    monkeypatch.setattr(uninstall.apikeys, "KNOWN", ("psi",))
    monkeypatch.setattr(uninstall.apikeys, "has_key", lambda s: True)
    monkeypatch.setattr(uninstall, "uninstaller_path", lambda: tmp_path / "unins000.exe")
    plan = {item.key: item for item in uninstall.plan()}
    assert set(plan) == {"tool:java", "config", "history", "keys", "program"}
    assert plan["tool:java"].default and not plan["tool:java"].personal and plan["program"].default
    assert all(not plan[k].default and plan[k].personal for k in ("config", "history", "keys"))


def test_the_dialog_needs_the_confirmation_and_one_choice_before_it_can_go_on():
    plan = [uninstall.PlanItem("cache", "Cache", "x", 10, True, False),
            uninstall.PlanItem("config", "Einstellungen", "y", 5, False, True)]
    dialog = uninstall_dialog.UninstallDialog(None, plan)
    assert dialog.selected() == {"cache"} and not dialog.go.isEnabled()
    dialog.confirm.setChecked(True)
    assert dialog.go.isEnabled()
    dialog.boxes["cache"].setChecked(False)
    assert dialog.selected() == set() and not dialog.go.isEnabled()
    dialog.boxes["config"].setChecked(True)
    assert dialog.selected() == {"config"} and dialog.go.isEnabled()
