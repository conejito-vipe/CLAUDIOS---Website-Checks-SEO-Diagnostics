"""Update-Prüfung gegen die Releases des eigenen Repositories (GitHub-API, nur HTTPS, nur github.com und githubusercontent.com).

Gesucht wird die neueste veröffentlichte Version (kein Entwurf, keine Vorabversion) mit einer Datei CLAUDIOS-Setup-<Version>.exe
und der Prüfsummen-Datei dazu (<Name>.sha256). Der Installer wird nur gestartet, wenn sein SHA256 zur Datei aus demselben Release
passt. Das schützt vor beschädigten Downloads, nicht vor einem übernommenen Konto (die Datei kommt vom selben Ort).
Das Format der GitHub-API ist Gedächtniswissen (tag_name, draft, prerelease, html_url, assets[].name, browser_download_url)."""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from .. import REPO_URL, USER_AGENT
from .errors import ClaudiosError, ErrorCode as E

SLUG = REPO_URL.removeprefix("https://github.com/").strip("/")
API_URL = f"https://api.github.com/repos/{SLUG}/releases/latest"
MAX_API = 300_000
MAX_SHA = 4096
MAX_SETUP = 400 * 1024 * 1024
REDIRECTS = {301, 302, 303, 307, 308}
INSTALLER = re.compile(r"^CLAUDIOS-Setup-\d+(?:\.\d+){1,3}\.exe$")
_VERSION = re.compile(r"^[vV]?(\d+(?:\.\d+){0,3})$")
_HEX = re.compile(r"\b[0-9a-fA-F]{64}\b")


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    page_url: str
    installer_name: str
    installer_url: str
    sha_url: str


def parse_version(text) -> tuple[int, ...] | None:
    match = _VERSION.match(str(text).strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def is_newer(latest, current) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def allowed_url(url: str) -> bool:
    parts = urlsplit(str(url))
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "github.com" or host.endswith((".github.com", ".githubusercontent.com")))


def pick_release(data) -> ReleaseInfo | None:
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    version = parse_version(data.get("tag_name", ""))
    if version is None:
        return None
    assets = {}
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str) and isinstance(asset.get("browser_download_url"), str):
            assets[asset["name"]] = asset["browser_download_url"]
    for name in sorted(assets):
        sha_url = assets.get(name + ".sha256")
        if INSTALLER.match(name) and sha_url and allowed_url(assets[name]) and allowed_url(sha_url):
            page = str(data.get("html_url", ""))
            return ReleaseInfo(".".join(str(part) for part in version), page if allowed_url(page) else REPO_URL,
                               name, assets[name], sha_url)
    return None


def parse_sha256(text: str) -> str:
    match = _HEX.search(text)
    return match.group(0).lower() if match else ""


def make_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(15.0, read=60.0), follow_redirects=False, trust_env=False,
                        headers={"User-Agent": USER_AGENT})


def _fetch(client, url: str, sink: Callable[[bytes], object], *, limit: int, accept: str = "*/*",
           cancel: threading.Event | None = None, progress: Callable[[int, int], None] | None = None) -> None:
    try:
        for _hop in range(6):
            if not allowed_url(url):
                raise ClaudiosError(E.DOWNLOAD_FAILED, reason="host not allowed")
            with client.stream("GET", url, headers={"Accept": accept}) as resp:
                if resp.status_code in REDIRECTS:
                    url = urljoin(url, resp.headers.get("location", ""))
                    continue
                if resp.status_code != 200:
                    raise ClaudiosError(E.DOWNLOAD_FAILED, reason=f"HTTP {resp.status_code}")
                try:
                    total = int(resp.headers.get("content-length") or 0)
                except ValueError:
                    total = 0
                done = 0
                for chunk in resp.iter_bytes(65536):
                    if cancel is not None and cancel.is_set():
                        raise ClaudiosError(E.INSTALL_CANCELLED)
                    done += len(chunk)
                    if done > limit:
                        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="file too large")
                    sink(chunk)
                    if progress is not None:
                        progress(done, total)
                return
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason="too many redirects")
    except httpx.HTTPError as exc:
        raise ClaudiosError(E.DOWNLOAD_FAILED, reason=type(exc).__name__) from None


def fetch_latest(client: httpx.Client | None = None) -> ReleaseInfo | None:
    """Die neueste Version oder None (kein Release, unlesbare Antwort)."""
    own = client is None
    http = client or make_client()
    buffer = bytearray()
    try:
        _fetch(http, API_URL, buffer.extend, limit=MAX_API, accept="application/vnd.github+json")
    except ClaudiosError as exc:
        if exc.ctx.get("reason") == "HTTP 404":
            return None
        raise
    finally:
        if own:
            http.close()
    try:
        return pick_release(json.loads(bytes(buffer)))
    except ValueError:
        return None


def download_installer(info: ReleaseInfo, folder: Path, *, progress: Callable[[int, int], None] | None = None,
                       cancel: threading.Event | None = None, client: httpx.Client | None = None) -> Path:
    """Lädt den Installer und prüft den SHA256. Bei jedem Fehler bleibt keine Teildatei zurück."""
    own = client is None
    http = client or make_client()
    dest = folder / info.installer_name
    try:
        sha_buffer = bytearray()
        _fetch(http, info.sha_url, sha_buffer.extend, limit=MAX_SHA, cancel=cancel)
        expected = parse_sha256(sha_buffer.decode("utf-8", "replace"))
        if not expected:
            raise ClaudiosError(E.CHECKSUM_MISMATCH, reason="no checksum")
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with dest.open("wb") as out:
            def sink(chunk: bytes) -> None:
                digest.update(chunk)
                out.write(chunk)

            _fetch(http, info.installer_url, sink, limit=MAX_SETUP, cancel=cancel, progress=progress)
        if digest.hexdigest() != expected:
            raise ClaudiosError(E.CHECKSUM_MISMATCH, reason=info.installer_name)
        return dest
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        if own:
            http.close()
