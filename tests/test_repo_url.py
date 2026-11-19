from pathlib import Path

from claudios import REPO_URL, USER_AGENT

ROOT = Path(__file__).resolve().parent.parent
OLD = "fuh" + "fux"  # der frühere Kontoname, hier absichtlich zerlegt
PROFILE = "https://github.com/conejito-vipe"


def test_the_repository_address_points_to_the_current_account():
    assert REPO_URL == PROFILE + "/CLAUDIOS---Website-Checks-SEO-Diagnostics"
    assert OLD not in REPO_URL.lower() and OLD not in USER_AGENT.lower() and REPO_URL in USER_AGENT


def test_both_licence_files_name_the_profile_and_have_no_placeholder_left():
    for name in ("LICENSE", "LICENSE.de.txt"):
        text = (ROOT / name).read_text("utf-8")
        assert PROFILE in text and "[GITHUB_PROFILE_URL]" not in text and OLD not in text.lower(), name
