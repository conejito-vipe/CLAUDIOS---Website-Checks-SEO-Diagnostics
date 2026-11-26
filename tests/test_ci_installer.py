"""Installer und Workflows: Aktualisierungsdialog wie bei CLAUDIA, gepinnte Actions, Prüfsummen-Abbruch, Geheimnis-Prüfung."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
ISS = (ROOT / "installer" / "claudios.iss").read_text("utf-8")


def test_every_action_is_pinned_to_a_commit():
    uses = [line.strip() for wf in WORKFLOWS for line in wf.read_text("utf-8").splitlines() if "uses:" in line]
    assert uses and all(re.search(r"@[0-9a-f]{40}\b", line) for line in uses), uses


def test_installer_asks_before_update_repair_or_downgrade_but_never_when_silent():
    app_id = re.search(r"AppId=\{\{([0-9A-F-]{36})\}", ISS).group(1)
    assert app_id in ISS.split("[Code]", 1)[1]  # der Deinstallations-Schlüssel gehört zur selben AppId
    for key in ("UpdateAsk", "SameAsk", "OlderAsk"):
        assert f"german.{key}=" in ISS and f"english.{key}=" in ISS
    code = ISS.split("InitializeSetup", 1)[1]
    assert code.index("WizardSilent") < code.index("MsgBox")  # stilles Update (im Programm) fragt nie nach
    assert "_internal" in ISS.split("[InstallDelete]", 1)[1].split("[", 1)[0]


def test_download_with_a_wrong_checksum_aborts_the_workflow_step():
    for name in ("zap-try.yml", "security.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text("utf-8")
        assert "sha256sum -c" in text and "exit 1" in text


def test_release_runs_tests_first_and_publishes_checksums_for_the_updater():
    text = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text("utf-8")
    assert "needs: tests" in text and "SHA256SUMS.txt" in text and ".sha256" in text
    assert "draft" in text and "prerelease" in text and "concurrency:" in text


def test_secret_scan_covers_the_whole_history_with_a_pinned_tool():
    text = (ROOT / ".github" / "workflows" / "security.yml").read_text("utf-8")
    assert "fetch-depth: 0" in text and "gitleaks" in text and "sha256sum -c" in text
    assert (ROOT / ".gitleaks.toml").is_file()


def test_linux_test_jobs_install_the_qt_system_libraries_first():
    for name in ("ci.yml", "build-windows.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text("utf-8")
        assert "libegl1" in text and text.index("libegl1") < text.index("pytest -q"), name
