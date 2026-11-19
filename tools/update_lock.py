"""Trägt Version, Adresse, Größe und SHA256 der Komponenten in die Lock-Datei ein.
Quellen: GitHub-Releases, Adoptium-API, nodejs.org. Die Dateien werden heruntergeladen und selbst gehasht;
liefert die Quelle eine eigene Prüfsumme, muss sie übereinstimmen.
Aufruf: python tools/update_lock.py [name ...]"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import httpx

LOCK = Path(__file__).resolve().parent.parent / "src" / "claudios" / "components" / "components.lock.json"


def github(client: httpx.Client, spec: dict) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = client.get(f"https://api.github.com/repos/{spec['repo']}/releases/latest", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    pattern = re.compile(spec["asset"])
    for asset in data.get("assets", []):
        if pattern.match(asset["name"]):
            return {"version": str(data["tag_name"]).lstrip("v"), "url": asset["browser_download_url"],
                    "size": asset.get("size", 0), "expected": None}
    names = ", ".join(a["name"] for a in data.get("assets", []))[:300]
    raise ValueError(f"kein Release-Asset passt zu {spec['asset']} (vorhanden: {names})")


def adoptium(client: httpx.Client, spec: dict) -> dict:
    resp = client.get(f"https://api.adoptium.net/v3/assets/latest/{spec['major']}/hotspot",
                      params={"architecture": "x64", "image_type": "jre", "os": "windows", "vendor": "eclipse"})
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError("Adoptium lieferte keine Treffer")
    package = data[0]["binary"]["package"]
    return {"version": data[0].get("release_name") or str(spec["major"]), "url": package["link"],
            "size": package.get("size", 0), "expected": package.get("checksum")}


def node(client: httpx.Client, _spec: dict) -> dict:
    resp = client.get("https://nodejs.org/dist/index.json")
    resp.raise_for_status()
    entry = next(e for e in resp.json() if e.get("lts") and "win-x64-zip" in e.get("files", []))
    version = entry["version"]
    filename = f"node-{version}-win-x64.zip"
    sums = client.get(f"https://nodejs.org/dist/{version}/SHASUMS256.txt")
    sums.raise_for_status()
    expected = next((ln.split()[0] for ln in sums.text.splitlines() if ln.strip().endswith(filename)), None)
    return {"version": version.lstrip("v"), "url": f"https://nodejs.org/dist/{version}/{filename}",
            "size": 0, "expected": expected}


RESOLVERS = {"github": github, "adoptium": adoptium, "node": node}


def sha256_of(client: httpx.Client, url: str) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        if resp.url.scheme != "https":
            raise ValueError("Download endete nicht auf HTTPS")
        for chunk in resp.iter_bytes(1 << 16):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def main() -> int:
    only = set(sys.argv[1:])
    raw = json.loads(LOCK.read_text("utf-8"))
    failures = 0
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, read=300.0), trust_env=False) as client:
        for entry in raw["components"]:
            name = entry["name"]
            if only and name not in only:
                continue
            try:
                spec = entry["resolver"]
                info = RESOLVERS[spec["type"]](client, spec)
                if not info["url"].startswith("https://"):
                    raise ValueError("Adresse ist nicht HTTPS")
                print(f"{name}: lade {info['url']}", flush=True)
                digest, size = sha256_of(client, info["url"])
                expected = (info.get("expected") or "").lower()
                if expected and expected != digest:
                    raise ValueError("Prüfsumme der Quelle weicht von der eigenen ab")
                entry.update(version=info["version"], url=info["url"], sha256=digest, size=size)
                print(f"OK      {name} {info['version']} {size} Bytes sha256={digest}")
            except Exception as exc:  # noqa: BLE001 – ein Fehler darf die anderen Komponenten nicht stoppen
                failures += 1
                print(f"FEHLER  {name}: {type(exc).__name__}: {exc}")
    LOCK.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"\n{failures} Fehler. Lock-Datei geschrieben: {LOCK}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())