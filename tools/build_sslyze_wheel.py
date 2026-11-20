"""Baut das sslyze-Wheel aus dem per Hash geprüften Eintrag in pip-sslyze.json (pip wheel --require-hashes) und schreibt
wheel-out/sslyze-wheel.json (Adresse im eigenen Release, SHA256, Größe) sowie wheel-out/tag.txt. Läuft im Workflow
„sslyze-Wheel erzeugen" auf dem Windows-Runner. Die Build-Werkzeuge (setuptools) holt pip in eine Hilfsumgebung und
prüft sie nicht gegen die Liste; die Prüfsumme des fertigen Wheels entsteht erst hier."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "src" / "claudios" / "components"
OUT = ROOT / "wheel-out"
DEFAULT_REPO = "conejito-vipe/CLAUDIOS---Website-Checks-SEO-Diagnostics"


def _helper():
    spec = importlib.util.spec_from_file_location("sslyzewheel", COMPONENTS / "sslyzewheel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    helper = _helper()
    text = json.loads((COMPONENTS / "pip-sslyze.json").read_text("utf-8"))["requirements"]
    block = helper.only_requirement(text, "sslyze")
    if "--hash=sha256:" not in block:
        print("::error::kein sslyze-Eintrag mit Prüfsumme in pip-sslyze.json")
        return 1
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "requirements.txt"
        req.write_text(block, "utf-8")
        proc = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--require-hashes",
                               "--disable-pip-version-check", "-w", str(OUT), "-r", str(req)], check=False)
    if proc.returncode != 0:
        print("::error::pip wheel ist fehlgeschlagen (Log darüber ansehen)")
        return 1
    wheels = sorted(OUT.glob("sslyze-*.whl"))
    if len(wheels) != 1 or not wheels[0].name.endswith("-py3-none-any.whl"):
        print(f"::error::erwartet genau ein sslyze-*-py3-none-any.whl, gefunden: {[w.name for w in wheels]}")
        return 1
    wheel = wheels[0]
    version = wheel.name.split("-")[1]
    tag = f"sslyze-wheel-{version}"
    repo = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    pin = {"version": version, "filename": wheel.name,
           "url": f"https://github.com/{repo}/releases/download/{tag}/{wheel.name}",
           "sha256": digest, "size": wheel.stat().st_size}
    (OUT / "sslyze-wheel.json").write_text(json.dumps(pin, indent=2) + "\n", "utf-8")
    (OUT / "tag.txt").write_text(tag, "utf-8")
    print(f"Wheel: {wheel.name}\nSHA256: {digest}\nTag: {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
