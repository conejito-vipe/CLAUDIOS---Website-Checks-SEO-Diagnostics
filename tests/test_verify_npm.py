import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tools" / "verify_npm.py"
spec = importlib.util.spec_from_file_location("verify_npm", PATH)
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def test_the_entry_file_comes_from_the_bin_field_and_stays_relative():
    assert live.bin_of({"bin": {"retire": "./lib/cli.js"}}, "retire") == "lib/cli.js"
    assert live.bin_of({"bin": "bin/x.js"}, "x") == "bin/x.js"
    for bad in ({"bin": {"a": "../evil.js"}}, {"bin": "/abs.js"}, {"bin": {}}, {}):
        assert live.bin_of(bad, "a") is None


def test_the_summaries_recognise_the_expected_findings_and_reject_junk():
    assert live.eslint_summary([{"messages": [{"ruleId": "security/detect-eval-with-expression"}]}])[0] is True
    assert live.eslint_summary([{"messages": []}])[0] is False and live.eslint_summary("x")[0] is False
    good = [{"warnings": [{"rule": "color-no-invalid-hex"}], "invalidOptionWarnings": []}]
    assert live.stylelint_summary(good)[0] is True
    bad = [{"warnings": [{"rule": "color-no-invalid-hex"}], "invalidOptionWarnings": [{"text": "x"}]}]
    assert live.stylelint_summary(bad)[0] is False and live.stylelint_summary(None)[0] is False
    hit = {"data": [{"results": [{"component": "jquery", "vulnerabilities": [{"severity": "medium"}]}]}]}
    assert live.retire_summary(hit)[0] is True
    assert live.retire_summary({"data": [{"results": [{"component": "jquery"}]}]})[0] is False
    assert live.retire_summary("x")[0] is False
