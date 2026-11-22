"""Fortschritt und Restzeit der Scan-Anzeige."""
from claudios.ui.scanprogress import PhaseClock, format_duration, overall_percent


def test_the_bar_grows_through_the_phases():
    values = [overall_percent("crawl", 6, 250), overall_percent("crawl", 60, 250), overall_percent("probe", 4, 8),
              overall_percent("link", 5, 10), overall_percent("check", 50, 100), overall_percent("check", 100, 100)]
    assert values == sorted(values) and values[1] == 40 and values[-1] == 100
    assert overall_percent("crawl", 999, 250) == 40 and overall_percent("check", 5, 0) == 100


def test_durations_are_readable():
    assert format_duration(5) == "5 s" and format_duration(125) == "2 min 5 s" and format_duration(-3) == "0 s"


def test_the_estimate_waits_for_the_first_steps_and_skips_the_crawl():
    clock = {"now": 0.0}
    phase = PhaseClock(lambda: clock["now"])
    assert phase.update("crawl", 10, 250) is None
    assert phase.update("check", 1, 100) is None
    clock["now"] = 10.0
    assert phase.update("check", 3, 100) == 10.0 / 2 * 98  # zwei fertig in 10 s, 98 offen
    assert phase.update("crawl", 11, 250) is None
