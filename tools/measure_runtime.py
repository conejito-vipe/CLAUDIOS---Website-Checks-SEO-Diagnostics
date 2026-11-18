"""Messung auf dem GitHub-Rechner (nicht im Programm): Python-Laufzeit für sslyze und Firefox/WebKit.
Ergebnisse stehen als Annotationen im Lauf. Der Aufruf meldet immer Exit-Code 0, damit alle Messungen laufen."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "src" / "claudios" / "components"
NPM = COMP / "npm"
PY_VERSION = "3.12.10"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"


def note(title: str, message: str, level: str = "notice") -> None:
    text = " ".join(str(message).split())[:700]
    print(f"::{level} title={title}::{text}")


def run(cmd: list, cwd: Path | None = None, timeout: float = 900.0, env: dict | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True, text=True,
                              errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__
    return proc.returncode, (proc.stdout + proc.stderr)[-600:]


def folder_mb(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1_048_576


def first_ipv4(host: str) -> str:
    try:
        return socket.getaddrinfo(host, 443, socket.AF_INET)[0][4][0]
    except OSError:
        return ""


def python_embed() -> None:
    work = Path(tempfile.mkdtemp())
    try:
        try:
            with urllib.request.urlopen(EMBED_URL, timeout=120) as resp:
                data = resp.read(60_000_000)
        except Exception as exc:  # noqa: BLE001
            note("Python-Embed", f"Download fehlgeschlagen ({type(exc).__name__}): {EMBED_URL}", "error")
            return
        digest = hashlib.sha256(data).hexdigest()
        note("Python-Embed SHA256", f"{PY_VERSION} amd64: {digest} ({len(data)} Bytes). Mit python.org vergleichen, "
                                    "dann pinnen.")
        runtime = work / "runtime"
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(runtime)
        pth = next(runtime.glob("python*._pth"), None)
        if pth is None:
            note("Python-Embed", "Keine ._pth-Datei im Archiv", "error")
            return
        lines = [x for x in pth.read_text("utf-8").splitlines() if x.strip() not in ("#import site", "import site")]
        pth.write_text("\n".join([*lines, "Lib\\site-packages", "import site"]) + "\n", "utf-8")
        reqs = json.loads((COMP / "pip-sslyze.json").read_text("utf-8")).get("requirements", "")
        if "--hash=sha256:" not in reqs:
            note("Python-Embed", "pip-sslyze.json enthält keine Prüfsummen", "error")
            return
        site = runtime / "Lib" / "site-packages"
        site.mkdir(parents=True)
        req_file = work / "requirements.txt"
        req_file.write_text(reqs, "utf-8")
        started = time.monotonic()
        code, tail = run([sys.executable, "-m", "pip", "install", "--require-hashes", "--no-deps",
                          "--only-binary=:all:", "--no-binary=sslyze", "--disable-pip-version-check",
                          "--target", site, "-r", req_file])
        note("pip --target", f"Exit {code} nach {time.monotonic() - started:.0f} s. {tail}",
             "notice" if code == 0 else "error")
        if code != 0:
            return
        embedded = runtime / "python.exe"
        code, tail = run([embedded, "-c", "import ssl, sys; print(sys.version.split()[0], ssl.OPENSSL_VERSION)"])
        note("Eingebettete Python", f"Exit {code}: {tail}", "notice" if code == 0 else "error")
        ip = first_ipv4("example.com")
        out = work / "result.json"
        code, tail = run([embedded, "-m", "sslyze", "--tlsv1_3", "--certinfo", "--json_out", out,
                          f"example.com:443{{{ip}}}"], cwd=work, timeout=300.0)
        status = "keine Ausgabe"
        try:
            first = json.loads(out.read_text("utf-8"))["server_scan_results"][0]
            status = str(first.get("scan_status"))
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            pass
        note("sslyze in eingebetteter Python", f"Exit {code}, scan_status={status}, IP {ip or '?'}. {tail[-200:]}",
             "notice" if status == "COMPLETED" else "error")
        note("Größe", f"Laufzeit mit sslyze: {folder_mb(runtime):.0f} MB entpackt")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def browsers() -> None:
    work = Path(tempfile.mkdtemp())
    try:
        node, npm = shutil.which("node"), shutil.which("npm")
        if not node or not npm:
            note("Browser", "node oder npm nicht gefunden", "error")
            return
        shutil.copy2(NPM / "pw-package.json", work / "package.json")
        shutil.copy2(NPM / "pw-package-lock.json", work / "package-lock.json")
        shutil.copy2(ROOT / "tools" / "measure_browsers.js", work / "measure_browsers.js")
        code, tail = run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=work)
        if code != 0:
            note("npm ci", f"Exit {code}. {tail}", "error")
            return
        env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(work / "browsers")}
        started = time.monotonic()
        code, tail = run([node, "node_modules/playwright/cli.js", "install", "firefox", "webkit"],
                         cwd=work, timeout=1500.0, env=env)
        note("Browser-Installation", f"Exit {code} nach {time.monotonic() - started:.0f} s, "
                                     f"{folder_mb(work / 'browsers'):.0f} MB. {tail[-200:]}",
             "notice" if code == 0 else "error")
        if code != 0:
            return
        out = work / "out.json"
        ip = first_ipv4("example.com")
        code, tail = run([node, "measure_browsers.js", ip, out], cwd=work, timeout=600.0, env=env)
        try:
            results = json.loads(out.read_text("utf-8"))
        except (OSError, ValueError):
            note("Browser-Messung", f"Exit {code}, keine Ausgabe. {tail}", "error")
            return
        for rec in results:
            note(f"Browser {rec.get('engine')}",
                 f"ok={rec.get('ok')} Version {rec.get('version')} HTTP {rec.get('status')} "
                 f"{rec.get('ms')} ms Titel '{rec.get('title')}' Fehler: {rec.get('error')}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "python-embed":
            python_embed()
        elif mode == "browsers":
            browsers()
        else:
            note("Messung", "Aufruf: python-embed oder browsers", "error")
    except Exception as exc:  # noqa: BLE001
        note("Messung", f"Unerwarteter Fehler: {type(exc).__name__} {exc}", "error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
