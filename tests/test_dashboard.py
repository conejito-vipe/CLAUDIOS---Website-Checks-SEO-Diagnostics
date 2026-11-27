"""Dashboard: Entwicklung je Domain aus dem Verlauf, Ort der Bildschirmfotos, Pro-Bereich."""
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from claudios.core import angebot, lizenz  # noqa: E402
from claudios.ui.page_dashboard import DashboardPage, category_trends, series  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _rec(day, score, cats, sev=2, count=3, hour=10):
    return {"saved": f"2026-11-{day:02d}T{hour:02d}:00:00+00:00", "score": score, "categories": cats, "host": "a.de",
            "findings": [{"check_id": "SEC-HDR-001", "severity": sev, "msg_de": "m", "msg_en": "m", "count": count}]}


def test_series_is_oldest_first_with_changes_and_counts_only_warnings_and_worse():
    pts = series([_rec(3, 80, {"Sicherheit": 90}), _rec(1, 60, {"Sicherheit": 70}), _rec(2, 70, {"Sicherheit": 75}, sev=1)])
    assert [p["score"] for p in pts] == [60, 70, 80]
    assert [p["delta"] for p in pts] == [None, 10, 10]
    assert [p["findings"] for p in pts] == [3, 0, 3]
    assert category_trends(pts) == [("Sicherheit", 70, 90)]
    assert category_trends(pts[:1]) == []


def test_the_page_groups_by_domain_and_names_the_screenshot_folder(monkeypatch, tmp_path):
    from claudios.ui import page_dashboard as pd

    groups = [("a.de", [("2026-11-01", [("10:00", _rec(1, 60, {"S": 1}))])]),
              ("b.de", [("2026-11-02", [("10:00", _rec(2, 90, {"S": 1})), ("09:00", _rec(2, 80, {"S": 1}, hour=9))])])]
    monkeypatch.setattr(pd, "grouped", lambda: groups)
    monkeypatch.setattr(pd, "shots_root", lambda: tmp_path / "shots")
    page = DashboardPage()
    page.retranslate()
    assert [page.domain.itemText(i) for i in range(page.domain.count())] == ["a.de", "b.de"]
    assert page.table.rowCount() == 1 and page.chart.values == [60]
    page.domain.setCurrentText("b.de")
    assert page.table.rowCount() == 2 and page.chart.values == [80, 90]
    assert str(tmp_path / "shots") in page.shots.text()
    monkeypatch.setattr(pd, "grouped", lambda: [])
    page.refresh()
    assert page.empty.text() and page.domain.isHidden()


def test_dashboard_and_expert_settings_are_pro_areas_but_not_locked_while_pro_is_off():
    ids = {f["id"]: f for f in angebot.FEATURES}
    assert ids["dashboard"]["normal"] is False and ids["dashboard"]["pro"] is True
    assert ids["experten"]["normal"] is False and ids["experten"]["pro"] is True
    assert {"dashboard", "experten"} <= set(lizenz.BEREICHE)
    assert angebot.AKTIV is False and lizenz.GESPERRT_OHNE_LIZENZ == ()
