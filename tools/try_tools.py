"""Richtet auf dem Rechner (GitHub-Mac) alle Werkzeug-Komponenten wirklich ein und startet jedes einmal.
Aufruf: python tools/try_tools.py [name ...]. Schreibt einen Bericht nach tools-report.json; Exit-Code 1 bei Fehlern.
Nutzt einen eigenen Datenordner (LOCALAPPDATA), berührt also keine echten Einstellungen."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="claudios-try-")

from claudios.components import manager  # noqa: E402
from claudios.components.lock import load_lock  # noqa: E402
from claudios.core.toolrunner import run_tool  # noqa: E402

HTML = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>t</title></head><body><p>x</p></body></html>'


def smoke(name: str) -> str:
    """Startet das Werkzeug einmal und gibt eine kurze Bestätigung zurück; wirft bei einem Fehler."""
    exe = manager.tool_path(name)
    java = manager.tool_path("java")
    tmp = Path(tempfile.mkdtemp(prefix="claudios-smoke-"))
    if name == "java":
        res = run_tool([exe, "-version"], cwd=tmp, timeout=60)
        return (res.stderr or res.stdout).splitlines()[0]
    if name == "node":
        return run_tool([exe, "--version"], cwd=tmp, timeout=60).stdout.strip()
    if name == "vnu":
        page = tmp / "t.html"
        page.write_text(HTML, "utf-8")
        res = run_tool([java, "-jar", exe, "--errors-only", str(page)], cwd=tmp, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(f"vnu Exit {res.returncode}: {res.stderr[:200]}")
        return "prüft eine Seite ohne Fehler"
    if name == "css-validator":
        return f"Datei da ({exe.stat().st_size} Bytes)"
    if name == "zap":
        res = run_tool([java, "-jar", exe, "-version"], cwd=tmp, timeout=180)
        return (res.stdout or res.stderr).strip().splitlines()[-1]
    if name == "python-runtime":
        return run_tool([exe, "--version"], cwd=tmp, timeout=60).stdout.strip()
    if name == "sslyze":
        out = tmp / "scan.json"
        res = run_tool([exe, "-m", "sslyze", "--tlsv1_3", "--certinfo", "--json_out", str(out), "example.com:443"],
                       cwd=tmp, timeout=180, extra_env={"PYTHONNOUSERSITE": "1"})
        data = json.loads(out.read_text("utf-8"))
        status = data["server_scan_results"][0].get("scan_status")
        if status != "COMPLETED":
            raise RuntimeError(f"sslyze Status {status}: {res.stderr[:200]}")
        return "sslyze Handshake mit example.com abgeschlossen"
    if name == "npm-tools":
        node = manager.tool_path("node")
        res = run_tool([node, exe, "--version"], cwd=tmp, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(f"eslint Exit {res.returncode}: {res.stderr[:200]}")
        return "eslint " + res.stdout.strip()
    if name == "playwright":
        node = manager.tool_path("node")
        res = run_tool([node, exe, "--version"], cwd=tmp, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(f"playwright Exit {res.returncode}: {res.stderr[:200]}")
        return "playwright " + res.stdout.strip()
    return "nicht geprüft"


def main() -> int:
    only = set(sys.argv[1:])
    report, failed = [], 0
    for comp in load_lock():
        if only and comp.name not in only:
            continue
        row = {"name": comp.name, "version": comp.version}
        start = time.time()
        try:
            manager.install(comp)
            row["status"] = manager.status(comp)
            if row["status"] != "installed":
                raise RuntimeError(f"Status {row['status']}")
            row["smoke"] = smoke(comp.name)
            row["ok"] = True
        except Exception as exc:  # noqa: BLE001 – jede Komponente einzeln melden
            failed += 1
            row.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        row["seconds"] = round(time.time() - start, 1)
        print(("OK     " if row["ok"] else "FEHLER ") + json.dumps(row, ensure_ascii=False), flush=True)
        report.append(row)
    Path("tools-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
