"""Schreibweise in den Beschriftungen von CSV, Excel und PDF: immer CLAUDIOS."""
from claudios.report.export_common import LABELS


def test_labels_use_the_upper_case_brand():
    for lang, table in LABELS.items():
        for key, value in table.items():
            assert "Claudios" not in value, (lang, key)
    assert LABELS["de"]["report"] == "CLAUDIOS-Bericht"
    assert LABELS["en"]["report"] == "CLAUDIOS report"
