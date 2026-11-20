import pytest

from claudios.i18n.strings import TEXTS

SAMPLE = "\n".join([
    "[SEC-HDR-001] Title", "Warum? in for if", "Code:", '@check("x")', "def f(x):", '    return "s" + 12  # note',
    '    """doc', 'more"""', "", "-" * 72, "", "Warum? in for if"])


@pytest.fixture
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


def ranges(block):
    return [(block.text()[r.start:r.start + r.length], r.format.foreground().color().name())
            for r in block.layout().formats()]


def color(name):
    from PySide6.QtGui import QColor

    from claudios.ui.highlight import COLORS

    return QColor(COLORS[name]).name()


def test_only_the_code_part_is_highlighted_as_python(qapp):
    from PySide6.QtGui import QTextDocument

    from claudios.ui.highlight import CodeHighlighter

    doc = QTextDocument()
    doc.setPlainText(SAMPLE)
    CodeHighlighter(doc).rehighlight()
    blocks = [doc.findBlockByNumber(i) for i in range(12)]
    assert (blocks[0].text(), color("header")) in ranges(blocks[0])
    assert ranges(blocks[1]) == [("Warum?", color("label"))]  # in/for/if im Fließtext bleiben ungefärbt
    assert ("@check", color("deco")) in ranges(blocks[3]) and ('"x"', color("string")) in ranges(blocks[3])
    assert ("def", color("keyword")) in ranges(blocks[4])
    assert [("return", color("keyword")), ('"s"', color("string")), ("12", color("number")),
            ("# note", color("comment"))] == ranges(blocks[5])
    assert blocks[6].userState() == 2 and blocks[7].userState() == 1  # Docstring über zwei Zeilen
    assert blocks[9].userState() == 0 and ranges(blocks[11]) == [("Warum?", color("label"))]


def test_main_window_has_no_setup_page_and_a_highlighted_technical_doc(qapp, env):
    from PySide6.QtGui import QSyntaxHighlighter

    from claudios.i18n.strings import get_lang, set_lang
    from claudios.ui.highlight import CodeHighlighter
    from claudios.ui.main_window import MainWindow

    old = get_lang()
    try:
        set_lang("de")
        window = MainWindow({"language": "de", "allow_localhost": False})
        assert "nav.setup" not in window.nav_keys and window.nav_keys[-1] == "nav.about"
        assert window.nav.count() == len(window.nav_keys) == len(window.pages) + 1
        doc = window.tech.view.document()
        highlighters = doc.findChildren(QSyntaxHighlighter)
        assert len(highlighters) == 1 and isinstance(highlighters[0], CodeHighlighter)
        highlighters[0].rehighlight()
        block = doc.firstBlock()
        while block.isValid() and not block.text().startswith("def "):
            block = block.next()
        assert block.isValid() and ("def", color("keyword")) in ranges(block)
        window.set_language("en")
    finally:
        set_lang(old)


def test_setup_texts_exist_in_both_languages():
    keys = ["nav.setup", "setup.title", "setup.intro", "setup.status", "setup.notes", "setup.finish"]
    for lang in ("de", "en"):
        for key in keys:
            assert TEXTS[lang][key].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
