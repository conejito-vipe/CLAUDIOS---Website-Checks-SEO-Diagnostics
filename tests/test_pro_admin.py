"""Schnittstelle zur Verwaltung (CONEJITO Admin): Lizenzschlüssel und Schaltdatei, signiert und offline geprüft; Pro-Seite inaktiv."""
from __future__ import annotations

import base64
import json
from datetime import date

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from PySide6.QtWidgets import QApplication

from claudios.core import angebot, lizenz, schalt
from claudios.ui import page_pro
from claudios.ui.main_window import MainWindow

_APP = QApplication.instance() or QApplication([])
TODAY = date(2026, 11, 26)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.fixture
def admin(monkeypatch, tmp_path):
    """Ein Schlüsselpaar der „Verwaltung“; das Programm kennt nur den öffentlichen Teil."""
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    monkeypatch.setattr(lizenz, "PUBLIC_KEYS", {"k1": public})
    monkeypatch.setattr(lizenz, "REVOKED_EXTRA", ())
    monkeypatch.setattr(lizenz, "SCHALT_AKTIV", False)

    class Admin:
        base = tmp_path

        @staticmethod
        def key(**over) -> str:
            data = {"kid": "k1", "id": "L1", "name": "Beispiel GmbH", "art": "gewerblich", "bis": "2027-01-01"} | over
            body = json.dumps(data).encode()
            return f"CL1.{b64(body)}.{b64(private.sign(body))}"

        @staticmethod
        def switch(serial=1, aktiv=True, blocked=(), prefix="SW1", purpose=schalt.PURPOSE) -> str:
            body = json.dumps({"v": 1, "kid": "k1", "aktiv": aktiv, "seit": "2026-11-01", "serial": serial,
                               "gesperrt": list(blocked)}).encode()
            return f"{prefix}.{b64(body)}.{b64(private.sign(purpose + body))}"

    return Admin


def test_shipped_state_has_no_key_and_nothing_is_locked(monkeypatch, tmp_path):
    assert lizenz.PUBLIC_KEYS == {} and lizenz.gesperrt_bereiche() == () and angebot.AKTIV is False
    assert lizenz.parse("CL1.e30.e30") == {"valid": False, "reason": "unbekannter Schlüssel"}  # ohne Schlüssel nie gültig
    assert all(lizenz.frei(tmp_path, area) for area in (*lizenz.BEREICHE, "pruefung"))
    assert angebot.state(tmp_path) == {"aktiv": False}  # keine Preise, nichts Sichtbares


def test_a_signed_key_is_valid_until_its_date_and_shows_the_remaining_days(admin):
    res = lizenz.parse(admin.key(), TODAY)
    assert res["valid"] and res["name"] == "Beispiel GmbH" and res["days_left"] == 36 and res["areas"] == "alle"
    assert lizenz.parse(admin.key(bis="2026-11-01"), TODAY)["reason"] == "abgelaufen"


@pytest.mark.parametrize("mutate,reason", [
    (lambda k: k[:-3] + ("AAA" if not k.endswith("AAA") else "BBB"), "Unterschrift ungültig"),
    (lambda k: k.replace("CL1.", "XX1.", 1), "Format"),
    (lambda k: k.split(".")[0] + "." + k.split(".")[1], "Format"),
    (lambda k: "", "leer oder zu lang"),
])
def test_tampered_or_malformed_keys_are_rejected(admin, mutate, reason):
    assert lizenz.parse(mutate(admin.key()), TODAY) == {"valid": False, "reason": reason}


def test_unknown_key_id_bad_data_and_other_signers_are_rejected(admin):
    assert lizenz.parse(admin.key(kid="k9"), TODAY)["reason"] == "unbekannter Schlüssel"
    assert lizenz.parse(admin.key(art="frei"), TODAY)["reason"] == "Angaben unvollständig"
    assert lizenz.parse(admin.key(bereiche=["nichts"]), TODAY)["reason"] == "Angaben unvollständig"
    assert lizenz.parse(admin.key(id="a b"), TODAY)["reason"] == "Angaben unvollständig"
    assert lizenz.parse(admin.key(bis="2026-13-45"), TODAY)["reason"] == "Angaben unvollständig"
    other = Ed25519PrivateKey.generate()
    body = json.dumps({"kid": "k1", "id": "L1", "name": "X", "art": "privat", "bis": "2027-01-01"}).encode()
    assert lizenz.parse(f"CL1.{b64(body)}.{b64(other.sign(body))}", TODAY)["reason"] == "Unterschrift ungültig"


def test_a_revoked_licence_is_invalid_and_store_keeps_only_usable_keys(admin):
    lizenz.REVOKED_EXTRA = ("L1",)
    assert lizenz.parse(admin.key(), TODAY)["reason"] == "gesperrt"
    lizenz.REVOKED_EXTRA = ()
    assert lizenz.store(admin.base, admin.key())["valid"] and lizenz.load(admin.base)
    assert not lizenz.store(admin.base, "CL1.kaputt")["valid"] and lizenz.load(admin.base) == admin.key()
    assert lizenz.remove(admin.base) and lizenz.load(admin.base) == "" and not lizenz.remove(admin.base)


def test_switch_file_turns_the_licence_duty_on_and_blocks_areas_without_a_key(admin):
    assert schalt.accept(admin.base, admin.switch(serial=1, aktiv=True, blocked=["L9"])) == ""
    assert lizenz.SCHALT_AKTIV and lizenz.REVOKED_EXTRA == ("L9",)
    assert lizenz.gesperrt_bereiche() == lizenz.BEREICHE and not lizenz.frei(admin.base, "export")
    assert lizenz.frei(admin.base, "pruefung")  # die Prüfung bleibt immer frei
    lizenz.store(admin.base, admin.key())
    assert lizenz.frei(admin.base, "export")  # ein gültiger Schlüssel öffnet alle Bereiche


def test_switch_file_never_goes_back_and_rejects_forgeries(admin):
    assert schalt.accept(admin.base, admin.switch(serial=5, aktiv=True)) == ""
    assert schalt.accept(admin.base, admin.switch(serial=4, aktiv=False)) != ""  # älter: nichts ändert sich
    assert lizenz.SCHALT_AKTIV and schalt.load(admin.base)["serial"] == 5
    assert schalt.accept(admin.base, admin.switch(serial=6, purpose=b"CONEJITO-LIZENZ\n")) != ""  # falscher Zweck
    assert schalt.accept(admin.base, admin.key()) != ""  # ein Lizenzschlüssel ist keine Schaltdatei
    assert schalt.accept(admin.base, admin.switch(serial=6, aktiv=False)) == "" and not lizenz.SCHALT_AKTIV


def test_fetch_is_https_only_needs_an_address_and_keeps_the_old_state_on_errors(admin):
    assert schalt.refresh(admin.base)["reason"] == "keine Adresse eingestellt"
    assert schalt.refresh(admin.base, "ftp://x/y")["reason"] == "nur https erlaubt"

    def broken(_url):
        raise OSError("kein Netz")

    assert schalt.refresh(admin.base, "https://admin.example/s.txt", fetch=broken)["reason"] == "nicht erreichbar"
    assert schalt.refresh(admin.base, "https://admin.example/s.txt", fetch=lambda _u: admin.switch(serial=2)) == {
        "ok": True, "reason": ""}
    assert schalt.load(admin.base)["serial"] == 2


def test_pro_page_is_hidden_and_disabled_until_the_administration_switches_it_on(admin, monkeypatch):
    window = MainWindow({"language": "de", "allow_localhost": False})
    row = window.nav_keys.index("nav.pro")
    assert window.nav.item(row).isHidden()
    page = next(p for p in window.pages if isinstance(p, page_pro.ProPage))
    assert page.banner.text() and not page.banner.isHidden()
    assert not any(w.isEnabled() for w in (page.key_input, page.save_btn, page.file_btn, page.fetch_btn))
    monkeypatch.setattr(angebot, "AKTIV", True)
    monkeypatch.setattr(page_pro, "data_dir", lambda: admin.base)
    page.retranslate()
    assert page.key_input.isEnabled() and page.save_btn.isEnabled() and not page.fetch_btn.isEnabled()  # ohne Adresse
    page.key_input.setText(admin.key())
    page.save_btn.click()
    assert "Beispiel GmbH" in page.lic_status.text() and page.key_input.text() == ""
    page.remove_btn.click()
    assert page.lic_status.text() == "Kein Schlüssel hinterlegt."
    assert page.table.rowCount() == len(angebot.FEATURES)
