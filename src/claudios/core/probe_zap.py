"""ZAP als passiver Proxy (nur Stufe 2). ZAP läuft als Daemon nur auf 127.0.0.1 (zufälliger Port, zufälliger
API-Schlüssel, ohne Update-Prüfung). Chromium (Playwright) lädt eine Stichprobe der Seiten durch ZAP; danach werden die
Funde der passiven Regeln abgefragt. Es wird nie ein aktiver Scan oder Spider gestartet. Der Verkehr liegt nur in
einem Zwischenordner, der danach gelöscht wird. Im Ergebnis stehen nur Regelname, Risiko, Adresse, CWE und Regel-ID,
nie der Beleg (er kann Cookie-Werte enthalten).
Vor und nach dem Lauf wird die DNS-Auflösung der Website erneut geprüft (core/rebind.py): zeigt sie auf eine nicht
öffentliche Adresse, gilt die Prüfung als nicht ausgeführt. Die von ZAP gesehenen Hosts werden nach dem Lauf
ebenfalls erneut aufgelöst (core/foreign.py): auffällige werden gemeldet, ihre Funde verworfen.
Die lokale Schnittstelle von ZAP ist unverschlüsselt (nur Loopback, der Dienst bietet nichts anderes an)."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from publicsuffix2 import get_sld

from .. import USER_AGENT, paths
from ..components.manager import tool_path
from ..components.npmtools import node_env
from . import foreign
from .errors import ClaudiosError
from .limits import LIMITS
from .rebind import recheck
from .redact import redact_url
from .toolrunner import ensure_in_tools, run_tool

NAME = "zap"
MIN_LEVEL = 2
SCHEME = "http"
HOST = "127.0.0.1"
PAGES = 10
READY_WAIT = 120.0
PASSIVE_WAIT = 120.0
MAX_ALERTS = 300
_KEEP_ENV = ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT")


class _Skip(Exception):
    """Der ZAP-Lauf konnte nicht stattfinden: die Prüfung gilt als nicht ausgeführt."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _pause(seconds: float) -> None:
    time.sleep(seconds)


def command(java, jar, home, port: int, key: str) -> list[str]:
    """Startkommando für ZAP. Muss mit dem Workflow zap-try.yml übereinstimmen (er ruft diese Funktion auf)."""
    return [str(java), "-Xmx768m", f"-Duser.home={home}", "-jar", str(jar), "-daemon", "-silent",
            "-host", HOST, "-port", str(port), "-dir", str(Path(home) / "zap"),
            "-config", f"api.key={key}", "-config", "start.checkForUpdates=false",
            "-config", "telemetry.enabled=false"]


def _tools():
    """(java, zap-jar, node) oder None, wenn etwas fehlt."""
    java, node = tool_path("java"), tool_path("node")
    zap_dir = paths.tools_dir() / "zap"
    jars = sorted(p for p in zap_dir.glob("**/zap-*.jar")
                  if p.name[4:-4].replace(".", "").isdigit()) if zap_dir.is_dir() else []
    browser = paths.tools_dir() / "playwright" / "node_modules" / "playwright"
    if java is None or node is None or not jars or not browser.is_dir():
        return None
    return java, jars[0], node


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _start_zap(java, jar, home, port: int, key: str):
    ensure_in_tools(java)
    env = {k: os.environ[k] for k in _KEEP_ENV if k in os.environ}
    try:
        return subprocess.Popen(
            command(java, jar, home, port, key), cwd=str(home), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        raise _Skip("zap_start_failed") from None


def _stop_zap(proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def _client(port: int, key: str) -> httpx.Client:
    return httpx.Client(base_url=f"{SCHEME}://{HOST}:{port}", headers={"X-ZAP-API-KEY": key},
                        timeout=httpx.Timeout(15.0), trust_env=False, follow_redirects=False)


def _json(client: httpx.Client, path: str, **params) -> dict:
    try:
        resp = client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        raise _Skip("zap_api_failed") from None
    if not isinstance(data, dict):
        raise _Skip("zap_api_failed")
    return data


def _wait_ready(client: httpx.Client, proc) -> str:
    deadline = time.monotonic() + READY_WAIT
    while True:
        if proc.poll() is not None:
            raise _Skip("zap_start_failed")
        try:
            resp = client.get("/JSON/core/view/version/")
            data = resp.json() if resp.status_code == 200 else None
            if isinstance(data, dict) and data.get("version"):
                return str(data["version"])[:20]
        except (httpx.HTTPError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise _Skip("zap_start_failed")
        _pause(1.0)


def _wait_passive(client: httpx.Client) -> bool:
    """True, wenn die Warteschlange der passiven Auswertung leer ist."""
    deadline = time.monotonic() + PASSIVE_WAIT
    while True:
        try:
            pending = int(_json(client, "/JSON/pscan/view/recordsToScan/").get("recordsToScan", 0))
        except (TypeError, ValueError):
            raise _Skip("zap_api_failed") from None
        if pending == 0:
            return True
        if time.monotonic() >= deadline:
            return False
        _pause(1.0)


def _alerts(client: httpx.Client, snap) -> list[dict]:
    raw = _json(client, "/JSON/core/view/alerts/", start="0", count="500").get("alerts")
    out: list[dict] = []
    for alert in raw if isinstance(raw, list) else []:
        if not isinstance(alert, dict):
            continue
        url = str(alert.get("url", ""))
        host = urlsplit(url).hostname or ""
        if host != snap.target.host and (get_sld(host) or host) != snap.target.registrable:
            continue  # Funde zu Fremdservern (Tracker, CDN) gehören nicht zur geprüften Website
        out.append({"name": str(alert.get("alert") or alert.get("name") or "?")[:120],
                    "risk": str(alert.get("risk", ""))[:20], "url": redact_url(url)[:200],
                    "cwe": str(alert.get("cweid", ""))[:10], "plugin": str(alert.get("pluginId", ""))[:10]})
        if len(out) >= MAX_ALERTS:
            break
    return out


def _seen_hosts(client) -> set[str]:
    """Hosts, die ZAP gesehen hat (ZAP-Schnittstelle core/view/hosts, Gedächtniswissen, ungeprüft). Ein Fehler
    heißt nur: unbekannt, der Lauf geht weiter."""
    try:
        raw = _json(client, "/JSON/core/view/hosts/").get("hosts")
    except Exception:  # noqa: BLE001
        return set()
    out: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        text = item.strip().lower()
        host = urlsplit(text if "://" in text else "//" + text).hostname
        if host:
            out.add(host.rstrip("."))
    return out


def _screen(result: dict, hosts: set[str], target_host: str, look=None) -> dict:
    """Prüft die gesehenen Hosts erneut. Auffällige werden gemeldet, ihre Funde verworfen."""
    found = foreign.screen(hosts, look or foreign.lookup, skip=(target_host,))
    if found.private:
        bad = set(found.private)
        result["alerts"] = [a for a in result["alerts"] if foreign.host_of(a["url"]) not in bad]
        result["foreign_private"] = list(found.private)
    if found.unchecked:
        result["foreign_unchecked"] = found.unchecked
    return result


def _browse(node, home, payload: dict) -> dict:
    """Startet das Browser-Skript (Node, Playwright) durch ZAP. Das Skript kommt aus dem Programmpaket."""
    home = Path(home)
    script = home / "zap_probe.js"
    script.write_bytes(resources.files("claudios.components").joinpath("npm").joinpath("zap_probe.js").read_bytes())
    source, target = home / "in.json", home / "out.json"
    source.write_text(json.dumps(payload), "utf-8")
    base = paths.tools_dir() / "playwright"
    env = node_env(Path(node).parent)
    env["NODE_PATH"] = str(base / "node_modules")
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(base / "browsers")
    timeout = min(LIMITS.browser_timeout_seconds * len(payload["urls"]) + 120.0, 1800.0)
    try:
        run_tool([node, script, source, target], cwd=home, timeout=timeout, extra_env=env)
    except ClaudiosError:
        raise _Skip("tool_failed") from None
    try:
        data = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError):
        raise _Skip("tool_output_unreadable") from None
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise _Skip("tool_output_unreadable")
    return data


def _session(client: httpx.Client, proc, snap, urls: list[str], node, home: Path, port: int) -> dict:
    version = _wait_ready(client, proc)
    scanners = _json(client, "/JSON/pscan/view/scanners/").get("scanners")
    if not isinstance(scanners, list) or not scanners:
        raise _Skip("zap_no_passive_rules")  # ohne passive Regeln wäre "keine Funde" ein falsches Bestanden
    try:
        resp = client.get("/OTHER/core/other/rootcert/")
        resp.raise_for_status()
    except httpx.HTTPError:
        raise _Skip("zap_api_failed") from None
    if b"BEGIN CERTIFICATE" not in resp.content:
        raise _Skip("zap_api_failed")
    pem = Path(home) / "zap-root.pem"
    pem.write_bytes(resp.content)
    payload = {"urls": urls, "registrable": snap.target.registrable, "proxy_port": port,
               "cert_path": str(pem), "ua_suffix": USER_AGENT}
    browser = _browse(node, home, payload)
    if browser.get("error") and not browser["pages"]:
        raise _Skip("browser_failed")
    complete = _wait_passive(client)
    result = {"skip": None, "zap_version": version, "scanners": len(scanners), "pages": len(browser["pages"]),
              "complete": complete, "alerts": _alerts(client, snap)}
    return _screen(result, _seen_hosts(client), snap.target.host)


def _remove(home: Path) -> None:
    for _attempt in range(5):  # Windows sperrt Dateien kurz nach dem Beenden des Prozesses
        shutil.rmtree(home, ignore_errors=True)
        if not home.exists():
            return
        _pause(1.0)


def _run(snap) -> dict:
    if snap.target.loopback:
        return {"skip": "localhost"}
    from ..checks._browser import sample_urls  # erst hier importiert: die Prüfungen laden die Probes, nicht umgekehrt

    urls = sample_urls(snap)[:PAGES]
    if not urls:
        return {"skip": "no_pages"}
    tools = _tools()
    if tools is None:
        return {"skip": "tool_not_found"}
    java, jar, node = tools
    home = Path(tempfile.mkdtemp(dir=paths.cache_dir()))
    proc = None
    try:
        port, key = _free_port(), secrets.token_hex(16)
        proc = _start_zap(java, jar, home, port, key)
        client = _client(port, key)
        try:
            return _session(client, proc, snap, urls, node, home, port)
        finally:
            client.close()
    except _Skip as skip:
        return {"skip": skip.reason}
    except ClaudiosError:
        return {"skip": "tool_failed"}
    finally:
        _stop_zap(proc)
        _remove(home)


def _real_gatekeeper(gk) -> bool:
    """Nur ein echter Gatekeeper hat Ziel, Auflösung und Seitenzuordnung. None und Testattrappen haben sie nicht."""
    return all(getattr(gk, name, None) is not None for name in ("target", "resolver", "same_site"))


async def _unchanged(gk) -> bool:
    """False, wenn die Website inzwischen auf eine nicht öffentliche Adresse zeigt (DNS-Rebinding)."""
    if not _real_gatekeeper(gk):
        return True  # nichts zu prüfen (im Programm ist der Gatekeeper immer echt)
    try:
        await recheck(gk)
    except ClaudiosError:
        return False
    return True


async def collect(gk, snap, resolver) -> dict:
    if snap.target.loopback:
        return await asyncio.to_thread(_run, snap)
    if not await _unchanged(gk):
        return {"skip": "dns_changed"}
    result = await asyncio.to_thread(_run, snap)
    if not await _unchanged(gk):
        return {"skip": "dns_changed"}  # die Ergebnisse stammen eventuell von einem fremden Server: verwerfen
    return result
