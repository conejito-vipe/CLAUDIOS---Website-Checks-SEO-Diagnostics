"""Festes sslyze-Wheel: Aufteilen der Anforderungsliste und Prüfung der Angaben (Adresse, SHA256, Dateiname)."""
import json

from claudios.components import sslyzewheel

TEXT = ("annotated-types==0.8.0 \\\n    --hash=sha256:aa \\\n    --hash=sha256:bb\n    # via pydantic\n"
        "sslyze==6.3.1 \\\n    --hash=sha256:cc\n    # via -r /tmp/req.in\n"
        "nassl==5.4.0 \\\n    --hash=sha256:dd\n    # via sslyze\n")


def test_only_requirement_keeps_just_the_tool():
    block = sslyzewheel.only_requirement(TEXT, "sslyze")
    assert "sslyze==6.3.1" in block and "--hash=sha256:cc" in block
    assert "nassl" not in block and "annotated" not in block


def test_without_requirement_keeps_the_dependencies():
    rest = sslyzewheel.without_requirement(TEXT, "sslyze")
    assert "sslyze==" not in rest and "--hash=sha256:cc" not in rest
    assert "nassl==5.4.0" in rest and "annotated-types==0.8.0" in rest and "--hash=sha256:bb" in rest


def _pin(**changes) -> str:
    data = {"version": "6.3.1", "filename": "sslyze-6.3.1-py3-none-any.whl", "url": "https://example.org/x.whl",
            "sha256": "a" * 64, "size": 10}
    data.update(changes)
    return json.dumps(data)


def test_valid_pin_is_accepted():
    pin = sslyzewheel.parse_pin(_pin())
    assert pin["sha256"] == "a" * 64 and pin["filename"].endswith(".whl")


def test_invalid_pins_are_rejected():
    assert sslyzewheel.parse_pin(_pin(url="http://example.org/x.whl")) == {}
    assert sslyzewheel.parse_pin(_pin(sha256="abc")) == {}
    assert sslyzewheel.parse_pin(_pin(filename="../x.whl")) == {}
    assert sslyzewheel.parse_pin(_pin(filename="x.zip")) == {}
    assert sslyzewheel.parse_pin("kein json") == {}
    assert sslyzewheel.parse_pin("[]") == {}
