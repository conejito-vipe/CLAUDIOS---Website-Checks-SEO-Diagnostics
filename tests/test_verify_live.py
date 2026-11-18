import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tools" / "verify_live.py"
spec = importlib.util.spec_from_file_location("verify_live", PATH)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def test_fingerprints_are_compared_by_service_and_text():
    ours = {"Heroku": ("no such app",), "Surge": ("project not found",), "Ghost": ("gone",)}
    theirs = [{"service": "Heroku", "fingerprint": "No such app"},
              {"service": "Surge.sh", "fingerprint": "something else"}]
    result = {service: state for service, state, _detail in live.compare_fingerprints(ours, theirs)}
    assert result == {"Heroku": "confirmed", "Surge": "differs", "Ghost": "not_listed"}


def test_bot_names_are_compared_without_case():
    missing, extra = live.compare_bots(["GPTBot", "ClaudeBot", "Nope"], ["gptbot", "CLAUDEBOT", "Other"])
    assert missing == ["Nope"] and extra == ["Other"]


def test_the_script_never_prints_the_api_key():
    assert "SB_KEY" in PATH.read_text("utf-8") and "print(key" not in PATH.read_text("utf-8")
