"""Befund-Erklärung: Text in beiden Sprachen, Registry-Texte, Klick auf Tabellenzeilen, Anbindung im Hauptfenster."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem  # noqa: E402

from claudios.checks import load_all  # noqa: E402
from claudios.i18n.strings import get_lang, set_lang, t, text  # noqa: E402
from claudios.ui import finding_detail  # noqa: E402
from claudios.ui.main_window import MainWindow  # noqa: E402

_app = QApplication.instance() or QApplication([])

META = SimpleNamespace(title={"de": "Titel", "en": "Title"}, why={"de": "Darum.", "en": "Because."},
                       fix="Behebe es. ## Fix it.", method={"de": "So.", "en": "Like this."},
                       logic={"de": "Logik.", "en": "Logic."},
                       refs=["https://example.test/a", "http://nope.test"])
GROUPS = [
    {"check_id": "SEC-HDR-001", "severity": 2, "msg_de": "Keine CSP", "msg_en": "No CSP", "count": 6,
     "example_urls": ["https://a.test/", "https://a.test/x"], "evidence": "Beleg-Text"},
    {"check_id": "SEC-HDR-001", "severity": 1, "msg_de": "Andere", "msg_en": "Other", "count": 1,
     "example_urls": [], "evidence": ""},
    {"check_id": "SEO-MET-001", "severity": 1, "msg_de": "Fremd", "msg_en": "Foreign", "count": 1,
     "example_urls": [], "evidence": ""},
]


def test_find_id_and_meta_text():
    assert finding_detail.find_id(["Warnung", "SEC-HDR-001", "x"]) == "SEC-HDR-001"
    assert finding_detail.find_id(["kein Treffer", None]) is None
    assert finding_detail.meta_text(META, "why", "en") == "Because."
    assert finding_detail.meta_text(META, "fix", "de") == "Behebe es."
    assert finding_detail.meta_text(META, "fix", "en") == "Fix it."
    assert finding_detail.meta_text(META, "gibt-es-nicht", "de") == ""
    assert finding_detail.meta_text(None, "why", "de") == ""


def test_the_clicked_finding_comes_first_and_only_https_links_are_shown():
    result = finding_detail.explain_text("SEC-HDR-001", GROUPS, ["Info", "SEC-HDR-001", "1", "Andere"], "de", META)
    assert "Titel (SEC-HDR-001)" in result
    assert result.index("Andere") < result.index("Keine CSP") and "Fremd" not in result
    assert "Beleg-Text" in result and "https://a.test/x" in result and "(6x)" in result
    assert "Darum." in result and "Behebe es." in result and "Fix it." not in result
    assert "https://example.test/a" in result and "nope.test" not in result


def test_the_english_text_uses_english_headings_and_texts():
    result = finding_detail.explain_text("SEC-HDR-001", GROUPS, [], "en", META)
    assert text("en", "detail.why") in result and "Fix it." in result and "Behebe" not in result
    assert "No CSP" in result


def test_without_details_the_text_says_so():
    result = finding_detail.explain_text("SEC-HDR-001", [], [], "de", None)
    assert text("de", "detail.none") in result and text("de", "detail.nometa") in result


def test_the_real_registry_explains_a_check():
    load_all()
    meta = finding_detail.meta_for("SEC-HDR-001")
    assert meta is not None
    assert finding_detail.meta_text(meta, "why", "de") and finding_detail.meta_text(meta, "fix", "de")
    result = finding_detail.explain_text("SEC-HDR-001", [], [], "de", meta)
    assert finding_detail.meta_text(meta, "title", "de") in result


def test_clicking_a_row_with_a_check_id_opens_the_explanation(monkeypatch):
    opened = []
    monkeypatch.setattr(finding_detail.FindingDialog, "exec", lambda self: opened.append(self.check_id) or 0)
    table = QTableWidget(2, 4)
    table.setHorizontalHeaderLabels(["Schwere", "Prüfung", "Anzahl", "Befund"])
    for col, value in enumerate(("Warnung", "SEC-HDR-001", "6", "Keine CSP")):
        table.setItem(0, col, QTableWidgetItem(value))
    for col, value in enumerate(("Info", "ohne ID", "1", "x")):
        table.setItem(1, col, QTableWidgetItem(value))
    linker = finding_detail.DetailLinker(None, lambda: None)
    linker.attach(table)
    linker.attach(table)  # mehrfaches Anhängen verbindet nicht doppelt
    table.cellClicked.emit(0, 1)
    table.cellClicked.emit(1, 0)
    assert opened == ["SEC-HDR-001"]
    assert table.toolTip() == t("detail.hint")


def test_the_main_window_links_its_result_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    old = get_lang()
    try:
        set_lang("de")
        window = MainWindow({"language": "de", "allow_localhost": False})
        assert window.last_result is None
        # kein Widget der Ergebnisseite darf eine Liste ohne Anbindung sein
        for table in window.results.findChildren(QTableWidget):
            assert table.property(finding_detail.FLAG)
    finally:
        set_lang(old)
