import re
from pathlib import Path

import claudios
from claudios.buildinfo import python_lines
from claudios.docs import render_doc
from claudios.i18n.strings import TEXTS, get_lang, n, set_lang, t


def test_german_and_english_have_identical_keys():
    assert set(TEXTS["de"]) == set(TEXTS["en"])
    assert all(value.strip() for lang in TEXTS.values() for value in lang.values())


def test_every_key_used_in_the_ui_exists():
    root = Path(claudios.__file__).parent
    files = list((root / "ui").glob("*.py")) + [root / "app.py", root / "docs.py"]
    patterns = [
        re.compile(r"""\b(?:t|lab)\(\s*['"]([a-z_]+\.[a-z_0-9.]+)['"]"""),
        re.compile(r"""\btext\(lang,\s*['"]([a-z_]+\.[a-z_0-9.]+)['"]"""),
        re.compile(r"""['"](splash\.[a-z_0-9]+)['"]"""),
    ]
    used = set()
    for path in files:
        source = path.read_text("utf-8")
        for rx in patterns:
            used.update(rx.findall(source))
    assert used, "no keys found, regex broken"
    assert used <= set(TEXTS["de"]), sorted(used - set(TEXTS["de"]))


def test_number_format_follows_language():
    old = get_lang()
    try:
        set_lang("de")
        assert n(12345) == "12.345" and n(2.5, 1) == "2,5"
        set_lang("en")
        assert n(12345) == "12,345" and n(2.5, 1) == "2.5"
        assert t("scan.start") == "Start scan"
    finally:
        set_lang(old)


def test_python_line_counter_finds_code():
    assert python_lines() > 500


def test_docs_are_generated_and_filterable():
    handbook = render_doc("handbook", "de")
    assert "SEC-HDR-001" in handbook and "Warum?" in handbook
    tech = render_doc("tech", "en")
    assert "def csp" in tech
    filtered = render_doc("handbook", "en", "hsts")
    assert "SEC-HDR-002" in filtered and "SEO-CAN-001" not in filtered
    assert "No matches" in render_doc("handbook", "en", "zzz-no-match")
