"""Seite 'Search Console': Schaltflächen-Zustände, Client- und CSV-Import, Anmeldung im Hintergrund, Stufe 2 (ohne Google)."""
from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from claudios.gsc import oauth
from claudios.i18n.strings import t
from claudios.ui import page_gsc

_APP = QApplication.instance() or QApplication([])


class Store:
    persistent = True


class FakeSession:
    def __init__(self):
        self.client, self.tokens, self.sites, self.level2, self.csv_pages = None, None, [], False, None
        self.store, self.calls = Store(), []

    @property
    def signed_in(self):
        return self.tokens is not None

    def load_saved(self):
        self.calls.append("load_saved")

    def eligible_sites(self):
        return [s for s in self.sites if s.get("permissionLevel") in ("siteOwner", "siteFullUser")]

    def set_client(self, client):
        self.client = client

    def set_tokens(self, tokens, remember):
        self.tokens = tokens
        self.calls.append(("tokens", remember))

    def list_sites(self):
        self.calls.append("list_sites")
        self.sites = [{"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"}]

    def sign_out(self):
        self.tokens, self.sites, self.level2 = None, [], False


@pytest.fixture
def env(monkeypatch, tmp_path):
    state = FakeSession()
    shown, answers = [], {"question": QMessageBox.StandardButton.Yes, "file": ""}
    monkeypatch.setattr(page_gsc.session, "SESSION", state)
    monkeypatch.setattr(page_gsc, "show_error", lambda _parent, info: shown.append(info))
    monkeypatch.setattr(page_gsc.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (answers["file"], "")))
    monkeypatch.setattr(page_gsc.QMessageBox, "question", staticmethod(lambda *a, **k: answers["question"]))
    page = page_gsc.GscPage()
    page.retranslate()
    return page, state, shown, answers, tmp_path


def finish(page):
    task = page._task
    if task is not None:
        task.wait(5000)
    _APP.processEvents()
    _APP.processEvents()


def client_file(tmp_path, content=None, name="client.json"):
    path = tmp_path / name
    path.write_text(content or json.dumps({"installed": {"client_id": "id", "client_secret": "sec"}}))
    return str(path)


def test_buttons_follow_the_state_without_client_and_when_signed_in(env):
    page, state, *_ = env
    assert page.client_lbl.text() == t("gsc.client.none") and not page.signin_btn.isEnabled()
    assert not page.signout_btn.isEnabled() and not page.refresh_btn.isEnabled() and not page.level2.isEnabled()
    state.client, state.tokens = oauth.Client("id", "sec"), object()
    state.sites = [{"siteUrl": "https://example.com/", "permissionLevel": "siteOwner"},
                   {"siteUrl": "https://x.org/", "permissionLevel": "siteRestrictedUser"}]
    page.refresh()
    assert page.signin_btn.isEnabled() and page.signout_btn.isEnabled() and page.refresh_btn.isEnabled()
    assert page.level2.isEnabled() and page.sites.count() == 2 and "(siteOwner)" in page.sites.item(0).text()
    state.store.persistent = False
    page.refresh()
    assert not page.remember.isEnabled() and page.remember.text() == t("gsc.remember_na")


def test_importing_a_valid_client_file_enables_sign_in(env):
    page, state, shown, answers, tmp = env
    answers["file"] = client_file(tmp)
    page.import_client()
    assert state.client == oauth.Client("id", "sec") and shown == [] and page.signin_btn.isEnabled()
    answers["file"] = ""  # Dialog abgebrochen: nichts ändert sich
    state.client = None
    page.import_client()
    assert state.client is None and shown == []


@pytest.mark.parametrize("content", ["kein json", json.dumps({"web": {}}), json.dumps({"installed": {"client_id": "x"}}),
                                     " " * (page_gsc.MAX_JSON + 10)])
def test_bad_or_oversized_client_files_show_an_error_and_import_nothing(env, content):
    page, state, shown, answers, tmp = env
    answers["file"] = client_file(tmp, content)
    page.import_client()
    assert state.client is None and len(shown) == 1


def test_an_unreadable_client_file_shows_an_error(env):
    page, state, shown, answers, tmp = env
    answers["file"] = str(tmp / "gibt-es-nicht.json")
    page.import_client()
    assert state.client is None and len(shown) == 1


def test_sign_in_runs_in_the_background_remembers_only_if_allowed_and_lists_the_sites(env, monkeypatch):
    page, state, shown, *_ = env
    state.client = oauth.Client("id", "sec")
    opened = []
    monkeypatch.setattr(page_gsc.oauth, "sign_in", lambda client, opener, cancel: opened.append((client, cancel)) or "T")
    page.remember.setChecked(True)
    page.sign_in()
    assert not page.signin_btn.isEnabled() and not page.import_btn.isEnabled()  # während der Anmeldung gesperrt
    page.sign_in()  # ein zweiter Klick startet keine zweite Anmeldung
    finish(page)
    assert len(opened) == 1 and ("tokens", True) in state.calls and "list_sites" in state.calls
    assert page.status.text().startswith("Angemeldet") and page._task is None and shown == []
    state.store.persistent = False
    state.tokens = None
    page.remember.setChecked(True)
    page.sign_in()
    finish(page)
    assert ("tokens", False) in state.calls  # ohne dauerhaften Speicher wird nie gespeichert


def test_a_failed_sign_in_shows_the_reason_and_unlocks_the_page(env, monkeypatch):
    page, state, shown, *_ = env
    state.client = oauth.Client("id", "sec")

    def boom(*_a, **_k):
        raise RuntimeError("Browser nicht gestartet")

    monkeypatch.setattr(page_gsc.oauth, "sign_in", boom)
    page.sign_in()
    finish(page)
    assert len(shown) == 1 and page.signin_btn.isEnabled() and state.tokens is None


def test_sign_out_clears_the_session_and_sign_in_without_client_does_nothing(env):
    page, state, *_ = env
    page.sign_in()
    assert page._task is None
    state.tokens, state.sites, state.level2 = object(), [{"siteUrl": "x", "permissionLevel": "siteOwner"}], True
    page.sign_out()
    assert not state.signed_in and state.sites == [] and page.status.text() == t("gsc.status.out")


def test_level2_needs_a_confirmation_and_stays_off_without_it(env):
    page, state, _shown, answers, _tmp = env
    state.client, state.tokens = oauth.Client("id", "sec"), object()
    state.sites = [{"siteUrl": "x", "permissionLevel": "siteOwner"}]
    page.refresh()
    answers["question"] = QMessageBox.StandardButton.No
    page.level2.setChecked(True)
    assert state.level2 is False and not page.level2.isChecked()
    answers["question"] = QMessageBox.StandardButton.Yes
    page.level2.setChecked(True)
    assert state.level2 is True and page.level2_lbl.text() == t("gsc.level2_on")
    page.level2.setChecked(False)  # Ausschalten fragt nicht nach
    assert state.level2 is False


def test_csv_import_accepts_a_page_list_and_reports_bad_files(env):
    page, state, shown, answers, tmp = env
    good = tmp / "pages.csv"
    good.write_text("Top pages,Clicks,Impressions,CTR,Position\nhttps://example.com/,10,100,10%,3.2\n", "utf-8")
    answers["file"] = str(good)
    page.import_csv()
    assert state.csv_pages and shown == [] and page.csv_lbl.text() != t("gsc.csv_hint")
    state.csv_pages = None
    big = tmp / "big.csv"
    big.write_bytes(b"x" * (page_gsc.csvimport.MAX_BYTES + 5))
    answers["file"] = str(big)
    page.import_csv()
    assert state.csv_pages is None and len(shown) == 1


def test_shutdown_cancels_a_running_task_and_waits_for_it(env, monkeypatch):
    page, state, *_ = env
    state.client = oauth.Client("id", "sec")
    seen = {}

    def slow(client, opener, cancel):
        seen["cancel"] = cancel
        cancel.wait(5)  # läuft, bis shutdown() abbricht
        raise RuntimeError("abgebrochen")

    monkeypatch.setattr(page_gsc.oauth, "sign_in", slow)
    monkeypatch.setattr(page_gsc, "show_error", lambda *a: None)
    page.sign_in()
    while "cancel" not in seen:
        _APP.processEvents()
    page.shutdown()
    assert seen["cancel"].is_set() and not page._task.isRunning()
    page.shutdown()  # ohne laufende Aufgabe: nichts passiert


def test_a_valid_client_file_padded_beyond_the_size_limit_is_still_refused(env):
    page, state, shown, answers, tmp = env
    valid = json.dumps({"installed": {"client_id": "id", "client_secret": "sec"}})
    answers["file"] = client_file(tmp, valid + " " * (page_gsc.MAX_JSON + 50))
    page.import_client()
    assert state.client is None and len(shown) == 1  # gültig, aber zu groß: abgelehnt


def test_a_failed_token_deletion_on_sign_out_is_shown_to_the_user(env):
    page, state, shown, *_ = env

    def broken():
        raise page_gsc.ClaudiosError(page_gsc.E.FS_ERROR, reason="credential delete")

    state.sign_out = broken
    page.sign_out()
    assert len(shown) == 1
