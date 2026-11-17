from pathlib import Path

from claudios.components.lock import load_lock

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS = {"java": "Temurin", "node": "Node.js", "vnu": "Nu Html Checker", "css-validator": "CSS Validator",
            "zap": "ZAP", "npm-tools": "ESLint", "sslyze": "sslyze", "playwright": "Playwright"}


def test_every_component_is_listed_in_the_third_party_notices():
    text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text("utf-8")
    for comp in load_lock():
        keyword = KEYWORDS.get(comp.name, comp.title.split()[0])  # neue Komponenten: erstes Wort des Titels
        assert keyword in text, f"component {comp.name}: add it to THIRD_PARTY_NOTICES.md (keyword: {keyword})"
    for extra in ("Stylelint", "retire.js", "PySide6", "AGPL-3.0", "axe-core", "Chromium"):
        assert extra in text


def test_readmes_show_the_logo_and_state_the_status():
    de = (ROOT / "README.de.md").read_text("utf-8")
    en = (ROOT / "README.en.md").read_text("utf-8")
    assert "assets/logo-full.png" in de and "assets/logo-full.png" in en
    assert (ROOT / "assets" / "logo-full.png").is_file()
    assert "simulierte" in de and "simulated" in en


def test_support_files_exist():
    for name in ("SECURITY.md", "FAQ.md", "CONTRIBUTING.md", "CHANGELOG.md", "CODE_OF_CONDUCT.md",
                 "LICENSE", ".github/dependabot.yml", ".github/pull_request_template.md"):
        assert (ROOT / name).is_file(), name
