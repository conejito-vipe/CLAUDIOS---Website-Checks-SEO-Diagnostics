"""Erzeugt eine einfache Stückliste (SBOM) im CycloneDX-1.5-JSON-Format: Python-Pakete der aktuellen Umgebung, npm-Pakete
aus den Sperrdateien, die Pakete der sslyze-Liste und die heruntergeladenen Werkzeuge mit ihren SHA256-Prüfsummen.
Aufruf: python tools/make_sbom.py [ausgabe.json]. Keine Abhängigkeiten außer der Standardbibliothek."""
from __future__ import annotations

import base64
import json
import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "src" / "claudios" / "components"
ALGORITHMS = {"sha512": "SHA-512", "sha384": "SHA-384", "sha256": "SHA-256", "sha1": "SHA-1"}
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;\\]+)", re.M)


def _integrity(value: str) -> list[dict]:
    algorithm, _, digest = value.partition("-")
    if algorithm not in ALGORITHMS:
        return []
    try:
        return [{"alg": ALGORITHMS[algorithm], "content": base64.b64decode(digest).hex()}]
    except ValueError:
        return []


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _app_version() -> str:
    try:
        text = (ROOT / "src" / "claudios" / "__init__.py").read_text("utf-8")
    except OSError:
        return "unknown"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "unknown"


def python_components() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name and name.lower() != "claudios":
            key = f"pypi:{name.lower()}:{dist.version}"
            found[key] = {"type": "library", "name": name, "version": dist.version,
                          "purl": f"pkg:pypi/{name.lower()}@{dist.version}"}
    return found


def sslyze_components() -> dict[str, dict]:
    text = _read_json(COMP / "pip-sslyze.json").get("requirements", "")
    found: dict[str, dict] = {}
    for name, version in _PIN.findall(text if isinstance(text, str) else ""):
        found[f"pypi:{name.lower()}:{version}"] = {
            "type": "library", "name": name, "version": version, "purl": f"pkg:pypi/{name.lower()}@{version}"}
    return found


def npm_components() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for lock in ("package-lock.json", "pw-package-lock.json"):
        packages = _read_json(COMP / "npm" / lock).get("packages")
        for key, value in (packages if isinstance(packages, dict) else {}).items():
            if not key.startswith("node_modules/") or not isinstance(value, dict) or not value.get("version"):
                continue
            name = key.rsplit("node_modules/", 1)[1]
            version = str(value["version"])
            purl_name = "%40" + name[1:] if name.startswith("@") else name
            entry = {"type": "library", "name": name, "version": version, "purl": f"pkg:npm/{purl_name}@{version}"}
            hashes = _integrity(str(value.get("integrity", "")))
            if hashes:
                entry["hashes"] = hashes
            found[f"npm:{name}:{version}"] = entry
    return found


def tool_components() -> dict[str, dict]:
    found: dict[str, dict] = {}
    items = _read_json(COMP / "components.lock.json").get("components")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entry = {"type": "application", "name": str(item["name"]), "version": str(item.get("version", "")) or "unpinned"}
        if item.get("sha256"):
            entry["hashes"] = [{"alg": "SHA-256", "content": str(item["sha256"])}]
        if item.get("url"):
            entry["externalReferences"] = [{"type": "distribution", "url": str(item["url"])}]
        found[f"tool:{item['name']}"] = entry
    return found


def build() -> dict:
    components: dict[str, dict] = {}
    for part in (python_components(), sslyze_components(), npm_components(), tool_components()):
        components.update(part)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {"type": "application", "name": "claudios", "version": _app_version()}},
        "components": [components[key] for key in sorted(components)],
    }


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "sbom.json")
    bom = build()
    target.write_text(json.dumps(bom, indent=2) + "\n", "utf-8")
    print(f"{len(bom['components'])} Bestandteile in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
