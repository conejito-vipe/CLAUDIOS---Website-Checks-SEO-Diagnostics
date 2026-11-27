"""Der Browser-Lauf (und damit die Barrierefreiheitsprüfung) darf nie ewig dauern: Grenzen je axe-Lauf, je Seite und gesamt."""
from pathlib import Path

from claudios.core.limits import LIMITS

JS = Path(__file__).resolve().parents[1] / "src" / "claudios" / "components" / "npm" / "browser_probe.js"


def test_the_limits_are_ordered_and_small():
    assert 0 < LIMITS.axe_timeout_seconds < LIMITS.browser_timeout_seconds < LIMITS.browser_total_seconds <= 600


def test_the_script_bounds_axe_each_page_and_the_whole_run_and_keeps_partial_results():
    source = JS.read_text("utf-8")
    assert 'AXE_MS, "axe")' in source                       # axe-core läuft nur begrenzt
    assert 'PAGE_MS, "page")' in source                     # jede Seite ist begrenzt
    assert "Date.now() > DEADLINE" in source                # der ganze Lauf ist begrenzt
    assert source.count("fs.writeFileSync(outPath") >= 2    # Zwischenstand nach jeder Seite


def test_the_python_side_hands_the_limits_to_the_script_and_kills_late():
    code = (JS.parents[2] / "checks" / "_browser.py").read_text("utf-8")
    for key in ("axe_timeout_ms", "page_timeout_ms", "total_ms"):
        assert key in code
    assert "LIMITS.browser_total_seconds + 60.0" in code
