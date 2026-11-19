from pathlib import Path

from claudios.i18n import strings_author
from claudios.i18n.strings import TEXTS
from claudios.report.report import PROMPT, render_html, render_summary

ROOT = Path(__file__).resolve().parent.parent
OLD = "fuh" + "fux"  # der frühere Autorenname, hier absichtlich zerlegt
FILES = ["README.md", "README.de.md", "assets/ASSETS.md", "assets/ASSETS.de.md", "THIRD_PARTY_NOTICES.md",
         "THIRD_PARTY_NOTICES.de.md", "installer/claudios.iss", "src/claudios/i18n/strings_author.py"]


def test_the_previous_author_name_is_gone_from_the_documents():
    for rel in FILES:
        assert OLD not in (ROOT / rel).read_text("utf-8").lower(), rel


def test_the_program_texts_and_the_installer_use_the_new_author():
    assert strings_author.AUTHOR == "conejito-vipe"
    for lang in ("de", "en"):
        for key in ("footer.before", "about.text", "about.licenses"):
            assert "conejito-vipe" in TEXTS[lang][key] and OLD not in TEXTS[lang][key].lower(), (lang, key)
    text = (ROOT / "installer" / "claudios.iss").read_text("utf-8")
    assert '#define AuthorName "conejito-vipe"' in text and "AppPublisher=GitHub - {#AuthorName}" in text


def rep(status, abort=None):
    return {"scan": {"target": "https://example.com/", "status": status, "pages_checked": 0, "bytes": 0, "abort": abort},
            "scores": {"overall": 93, "categories": {"SYS": 93}}, "findings": [], "checks": []}


def test_an_aborted_scan_shows_no_overall_score_in_the_reports():
    info = {"de": {"title": "T", "cause": "C", "action": "A"}, "en": {"title": "T", "cause": "C", "action": "A"}}
    for lang, word in (("de", "keine"), ("en", "none")):
        aborted = rep("aborted", info)
        assert "/100" not in render_summary(aborted, lang) and word in render_summary(aborted, lang)
        assert "/100" not in render_html(aborted, lang)
        assert "93/100" in render_summary(rep("complete"), lang) and "93/100" in render_html(rep("complete"), lang)


def test_the_prompts_use_the_new_spelling():
    assert "CLAUDIOS" in PROMPT["de"] and "CLAUDIOS" in PROMPT["en"] and "Answer in English" in PROMPT["en"]
