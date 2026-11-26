"""Prüft auf dem GitHub-Rechner (nicht im Programm), ob jede Komponente der Sperrdatei noch zu ihrer Prüfsumme passt.
Lädt jede Adresse mit Prüfsumme (nur https), vergleicht SHA256 und Größe und schreibt das Ergebnis als Annotation (nur
Abweichungen) und in die Zusammenfassung des Laufs. Meldet immer Exit-Code 0."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

LOCK = Path(__file__).resolve().parent.parent / "src" / "claudios" / "components" / "components.lock.json"
LIMIT = 800 * 1024 * 1024


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:700]}")


def fetch(url: str) -> dict:
    """Lädt die Adresse und gibt Prüfsumme, Größe, Endadresse und die ersten Bytes zurück."""
    request = urllib.request.Request(url, headers={"User-Agent": "Claudios-verify"})
    digest, size, head = hashlib.sha256(), 0, b""
    with urllib.request.urlopen(request, timeout=300) as resp:
        final, ctype = resp.geturl(), resp.headers.get("content-type", "")
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            if not head:
                head = chunk[:4]
            size += len(chunk)
            if size > LIMIT:
                raise ValueError("Datei größer als 800 MB")
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": size, "final": final, "ctype": ctype, "head": head}


def verdict(item: dict, got: dict) -> str:
    expected = str(item.get("sha256", "")).lower()
    return "ok" if got["sha256"] == expected else "differs"


def main() -> int:
    try:
        items = json.loads(LOCK.read_text("utf-8")).get("components", [])
    except (OSError, ValueError) as exc:
        note("error", "Sperrdatei", f"nicht lesbar: {type(exc).__name__}")
        return 0
    rows = ["| Komponente | Ergebnis | erwartet | erhalten | Größe (Sperrdatei / Download) | Endadresse |", "|---|---|---|---|---|---|"]
    bad = 0
    flat = []
    for item in items:
        flat.append(item)
        for system, extra in (item.get("variants") or {}).items():
            flat.append({**item, **extra, "name": f"{item.get('name')} ({system})"})
    items = flat
    for item in items:
        name, url = str(item.get("name")), str(item.get("url", ""))
        if not item.get("sha256") or not url.startswith("https://"):
            rows.append(f"| {name} | nicht gepinnt | | | | |")
            continue
        try:
            got = fetch(url)
        except Exception as exc:  # noqa: BLE001 – eine Komponente darf die anderen nicht stoppen
            bad += 1
            note("error", f"{name}", f"Download fehlgeschlagen ({type(exc).__name__}): {url}")
            rows.append(f"| {name} | Download fehlgeschlagen | | | | {url} |")
            continue
        state = verdict(item, got)
        rows.append(f"| {name} | {state} | `{str(item['sha256'])[:16]}…` | `{got['sha256'][:16]}…` | "
                    f"{item.get('size')} / {got['size']} | {got['final']} |")
        if state != "ok":
            bad += 1
            note("error", f"{name} weicht ab",
                 f"erwartet {item['sha256'][:16]}…, erhalten {got['sha256'][:16]}… ({got['size']} Bytes, "
                 f"Typ {got['ctype']}, Anfang {got['head']!r}). Adresse in der Sperrdatei: {url}")
    note("notice", "Sperrdatei", f"{len(items)} Komponenten geprüft, {bad} mit Problem")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
