from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text("utf-8")


def test_suggestions_are_welcome_and_match_the_license():
    for name in ("CONTRIBUTING.md", "CONTRIBUTING.de.md", ".github/pull_request_template.md"):
        text = read(name)
        assert "not accepted" not in text and "nicht angenommen" not in text, name
    assert "3b" in read("CONTRIBUTING.md") and "3b" in read("CONTRIBUTING.de.md")
    assert "welcome" in read(".github/pull_request_template.md")
    assert "CLAUDIOS.log" in read("CONTRIBUTING.md") and "CLAUDIOS.log" in read("CONTRIBUTING.de.md")
