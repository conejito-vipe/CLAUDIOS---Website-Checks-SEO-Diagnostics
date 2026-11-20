"""Der Export-Dialog weist auf das Scan-Protokoll und die Sperre hin (beide Sprachen, Sperrzeit aus limits.py)."""
from claudios.core.limits import LIMITS
from claudios.i18n.strings import TEXTS, text


def test_export_text_warns_about_the_scan_log_and_keeps_its_placeholder():
    hours = str(LIMITS.audit_tamper_lock_seconds // 3600)
    for lang in ("de", "en"):
        raw = TEXTS[lang]["export.text"]
        assert "audit.jsonl" in raw and hours in raw and "{files}" in raw
        assert "datei-a.zip" in text(lang, "export.text", files="datei-a.zip")
