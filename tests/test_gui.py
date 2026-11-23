import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_startup_steps_succeed(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from claudios.app import startup_steps

    state = {}
    for _key, _weight, func in startup_steps(state):
        func()
    assert state["audit_ok"] is True


def test_main_window_builds_and_switches_language(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from claudios.i18n.strings import get_lang, set_lang
    from claudios.ui.main_window import MainWindow

    old = get_lang()
    try:
        set_lang("de")
        window = MainWindow({"language": "de", "allow_localhost": False})
        assert window.nav.item(0).text() == "Scan"
        assert window.nav.item(2).text() == "Hilfe"
        assert window.footer.after.text().endswith("Zeilen Python")
        window.set_language("en")
        assert window.nav.item(2).text() == "Help"
        assert window.footer.after.text().endswith("lines of Python")
        assert not window.confirm_checked() if hasattr(window, "confirm_checked") else True
        assert window.scan.confirm.isChecked() is False
    finally:
        set_lang(old)


def test_error_info_uses_catalog(qapp):
    from claudios.core.errors import ClaudiosError, ErrorCode
    from claudios.ui.dialogs import error_info

    info = error_info(ClaudiosError(ErrorCode.TLS_CERT, host="example.com", reason="expired"))
    assert info["code"] == "CLA-TLS-001" and "expired" in info["cause"]
    assert error_info(ValueError("x"))["code"] == "CLA-INT-001"
