from pathlib import Path

from claudios.i18n import strings_author
from claudios.i18n.strings import TEXTS

ROOT = Path(__file__).resolve().parent.parent
WRONG = "vi" + "pecoded"  # die falsche Schreibweise, hier absichtlich zerlegt
RIGHT = "vi" + "becoded"
FILES = ["README.md", "README.de.md", "src/claudios/i18n/strings_author.py"]


def test_the_word_is_spelled_vibecoded_in_the_documents_and_the_program_texts():
    for rel in FILES:
        text = (ROOT / rel).read_text("utf-8").lower()
        assert WRONG not in text, rel
        assert RIGHT in text, rel
    for lang in ("de", "en"):
        for key in ("footer.before", "about.text"):
            assert RIGHT in TEXTS[lang][key].lower() and WRONG not in TEXTS[lang][key].lower(), (lang, key)
    assert strings_author.AUTHOR == "conejito-vipe"
