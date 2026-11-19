from pathlib import Path

from claudios.i18n.strings import TEXTS

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text("utf-8")


def test_the_licence_states_the_three_prohibitions_in_both_languages():
    english, german = read("LICENSE").lower(), read("LICENSE.de.txt").lower()
    for word in ("commercial use", "modification", "distribution", "political parties"):
        assert word in english, word
    for word in ("kommerzielle nutzung", "veränderung", "weitergabe", "politische parteien"):
        assert word in german, word
    assert "mit license" not in english and "permission is hereby granted" not in english


def test_no_document_or_setting_still_claims_the_mit_licence_for_the_code():
    assert "MIT" not in read("pyproject.toml")
    assert "MIT for the code" not in read("README.md") and "MIT für den Code" not in read("README.de.md")
    assert "itself is MIT-licensed" not in read("THIRD_PARTY_NOTICES.md")
    assert "selbst steht unter der MIT-Lizenz" not in read("THIRD_PARTY_NOTICES.de.md")
    for rel in ("SECURITY.md", "SECURITY.de.md", "THREAT_MODEL.md", "THREAT_MODEL.de.md"):
        assert "is open source" not in read(rel).lower() and "ist open source" not in read(rel).lower(), rel
    for lang in ("de", "en"):
        assert "MIT-Lizenz" not in TEXTS[lang]["about.licenses"] and "MIT licence" not in TEXTS[lang]["about.licenses"]


def test_the_documents_point_to_the_licence_and_the_installer_shows_it_per_language():
    for rel in ("README.md", "README.de.md"):
        assert "LICENSE" in read(rel), rel
    iss = read("installer/claudios.iss")
    assert 'LicenseFile: "..\\LICENSE.de.txt"' in iss and 'LicenseFile: "..\\LICENSE"' in iss
    assert "LICENSE.de.txt" in iss.split("[Files]")[1]


def test_code_contributions_are_declined():
    assert "pull requests with code are not accepted" in read("CONTRIBUTING.md")
    assert "Pull Requests mit Code nicht angenommen" in read("CONTRIBUTING.de.md")
