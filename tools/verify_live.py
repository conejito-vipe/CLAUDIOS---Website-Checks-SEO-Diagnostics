"""Praxisprüfung auf dem GitHub-Rechner (nicht im Programm): misst, was bisher nur aus dem Gedächtnis im Code steht.
Aufruf: python tools/verify_live.py <modus> mit rdap, psi, safebrowsing, fingerprints, bots, licenses oder all.
Ergebnisse stehen als Annotationen im Lauf. Der Aufruf meldet immer Exit-Code 0, damit alle Messungen laufen.
Safe Browsing und PageSpeed nutzen die Schlüssel aus den Umgebungsvariablen SB_KEY und PSI_KEY, falls gesetzt; sie
werden nie ausgegeben."""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

UA = "Claudios-verify"
FINGERPRINT_URL = "https://raw.githubusercontent.com/EdOverflow/can-i-take-over-xyz/master/fingerprints.json"
BOT_URLS = ("https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/robots.json",
            "https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/robots.txt")
KEYWORD = {"GitHub Pages": "github", "Heroku": "heroku", "AWS S3": "aws", "Shopify": "shopify", "Surge": "surge",
           "Bitbucket": "bitbucket", "Ghost": "ghost", "Fastly": "fastly"}
PYPI = ("openpyxl", "et-xmlfile", "pip", "pyinstaller", "sslyze", "httpx", "beautifulsoup4", "dnspython",
        "publicsuffix2", "PySide6")
NPM = ("eslint", "eslint-plugin-security", "stylelint", "retire", "playwright", "axe-core")
GITHUB = ("w3c/css-validator", "validator/validator", "zaproxy/zaproxy", "nodejs/node", "adoptium/temurin-build",
          "pyinstaller/pyinstaller", "jrsoftware/issrc", "nabla-c0d3/sslyze", "dequelabs/axe-core",
          "microsoft/playwright", "python/cpython", "pypa/pip", "eslint-community/eslint-plugin-security",
          "retirejs/retire.js")


def note(level: str, title: str, message: object) -> None:
    print(f"::{level} title={title}::{' '.join(str(message).split())[:700]}")


def fetch(url: str, accept: str = "*/*"):
    """(Status, Inhaltstyp, JSON oder None, Textanfang). Status None bei einem Verbindungsfehler."""
    try:
        resp = httpx.get(url, headers={"Accept": accept, "User-Agent": UA}, timeout=40.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        return None, "", None, type(exc).__name__
    try:
        data = resp.json()
    except ValueError:
        data = None
    return resp.status_code, resp.headers.get("content-type", ""), data, resp.text[:200]


def compare_fingerprints(ours: dict, theirs: list) -> list[tuple[str, str, str]]:
    """Je Dienst: confirmed (unser Text steht in der öffentlichen Liste), differs oder not_listed."""
    out = []
    for service, signs in sorted(ours.items()):
        key = KEYWORD.get(service, service.split()[0].lower())
        entries = [e for e in theirs if isinstance(e, dict) and key in str(e.get("service", "")).lower()]
        if not entries:
            out.append((service, "not_listed", ""))
            continue
        texts = [str(e.get("fingerprint", "")).lower() for e in entries]
        hit = any(sign in text or (text and text in sign) for sign in signs for text in texts)
        out.append((service, "confirmed" if hit else "differs", " | ".join(text[:70] for text in texts[:2])))
    return out


def compare_bots(ours: list[str], names: list[str]) -> tuple[list[str], list[str]]:
    """(unsere Namen, die in der Liste fehlen; Namen der Liste, die wir nicht haben)."""
    theirs = {n.lower() for n in names}
    mine = {b.lower() for b in ours}
    return [b for b in ours if b.lower() not in theirs], sorted(n for n in names if n.lower() not in mine)


def rdap() -> None:
    from claudios.core import probe_rdap

    accept = "text/html,application/xhtml+xml,*/*;q=0.5"  # genau der Header des Gatekeepers
    status, ctype, data, snippet = fetch(probe_rdap.BOOTSTRAP, accept)
    note("notice" if status == 200 and data else "error", "RDAP IANA-Liste",
         f"HTTP {status}, {ctype}, JSON={'ja' if data else 'nein'}, "
         f"Schlüssel={sorted(data)[:5] if isinstance(data, dict) else snippet}")
    server = probe_rdap.server_for(data, "com") if data else None
    note("notice" if server else "error", "RDAP Server für com", server or "nicht gefunden (Format der Liste anders?)")
    if not server:
        return
    for label, header in (("Gatekeeper-Header", accept), ("rdap+json", "application/rdap+json")):
        status, ctype, answer, snippet = fetch(f"{server}domain/example.com", header)
        parsed = probe_rdap.parse_domain(answer) if isinstance(answer, dict) else None
        keys = sorted(answer)[:8] if isinstance(answer, dict) else snippet
        note("notice" if parsed and parsed["expires"] else "warning", f"RDAP Domain ({label})",
             f"HTTP {status}, {ctype}, Felder={keys}, geparst={parsed}")


def psi() -> None:
    import json

    from claudios.core import probe_psi, thirdparty
    from claudios.core.errors import ClaudiosError

    key = os.environ.get("PSI_KEY", "").strip()
    params = [("url", "https://example.com/"), ("strategy", "mobile")] + [("category", c) for c in probe_psi.CATEGORIES]
    if key:
        params.append(("key", key))
    try:
        status, raw, truncated = asyncio.run(thirdparty.request(
            "GET", probe_psi.ENDPOINT, params=params, max_bytes=3_000_000, timeout=90.0))
    except ClaudiosError as exc:
        note("error", "PageSpeed", f"Verbindung fehlgeschlagen: {exc.code.value}")
        return
    label = "mit Schlüssel" if key else "ohne Schlüssel"
    if status != 200:
        text = raw[:150].decode("utf-8", errors="replace")
        text = text.replace(key, "***") if key else text
        note("warning", f"PageSpeed {label}", f"HTTP {status} (429 heißt: Kontingent erschöpft), Anfang: {text}")
        return
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        note("error", f"PageSpeed {label}", "Antwort ist kein JSON")
        return
    parsed = probe_psi.parse(data)
    note("notice" if parsed else "error", f"PageSpeed Antwort {label}",
         f"abgeschnitten={truncated}, oberste Felder={sorted(data)[:8]}, geparst={parsed}")


def safebrowsing() -> None:
    import json

    from claudios.core import probe_safebrowsing, thirdparty
    from claudios.core.errors import ClaudiosError

    key = os.environ.get("SB_KEY", "").strip()
    urls = ["https://example.com/"] + (["https://testsafebrowsing.appspot.com/s/malware.html"] if key else [])
    try:
        status, raw, _truncated = asyncio.run(thirdparty.request(
            "POST", probe_safebrowsing.ENDPOINT, params={"key": key} if key else None,
            json_body=probe_safebrowsing._body(urls), max_bytes=200_000, timeout=30.0))
    except ClaudiosError as exc:
        note("error", "Safe Browsing", f"Verbindung fehlgeschlagen: {exc.code.value}")
        return
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        data = {}
    if key:
        matches = [m.get("threatType") for m in data.get("matches", []) if isinstance(m, dict)]
        note("notice" if status == 200 else "warning", "Safe Browsing mit Schlüssel",
             f"HTTP {status}, Treffer={matches}, Felder={sorted(data)[:5]}")
    else:
        error = data.get("error") if isinstance(data, dict) else None
        detail = ({k: str(error.get(k))[:60] for k in ("code", "status", "message")}
                  if isinstance(error, dict) else raw[:100])
        note("notice" if status in (400, 401, 403) else "warning", "Safe Browsing ohne Schlüssel",
             f"HTTP {status} (4xx mit Fehlerantwort heißt: Endpunkt erreichbar), Antwort={detail}")


def fingerprints() -> None:
    from claudios.core import probe_passive

    status, _ctype, data, snippet = fetch(FINGERPRINT_URL)
    if status != 200 or not isinstance(data, list):
        note("error", "Fingerprint-Liste", f"HTTP {status}, kein Array: {snippet}")
        return
    rows = compare_fingerprints(probe_passive.FINGERPRINTS, data)
    first = sorted(data[0])[:8] if isinstance(data[0], dict) else "?"
    note("notice", "Fingerprint-Liste", f"{len(data)} Einträge, Felder des ersten: {first}")
    for service, state, detail in rows:
        note("notice" if state == "confirmed" else "warning", f"Fingerprint {service}", f"{state}. Liste: {detail}")


def bots() -> None:
    from claudios.checks.ai_visibility import AI_BOTS

    names: list[str] = []
    for url in BOT_URLS:
        status, _ctype, data, _text = fetch(url)
        if status == 200 and isinstance(data, dict):
            names = list(data)
        elif status == 200:
            body = httpx.get(url, headers={"User-Agent": UA}, timeout=40.0, follow_redirects=True).text
            names = [line.split(":", 1)[1].strip() for line in body.splitlines()
                     if line.lower().startswith("user-agent:")]
        if names:
            note("notice", "Bot-Liste Quelle", f"{url.rsplit('/', 1)[-1]}: {len(names)} Namen")
            break
    if not names:
        note("error", "Bot-Liste", "keine der Adressen lieferte Namen")
        return
    missing, extra = compare_bots([name for name, _operator in AI_BOTS], names)
    note("warning" if missing else "notice", "Bot-Namen",
         f"In der Liste nicht gefunden: {missing or 'keiner'}. In der Liste, aber nicht bei uns (erste 25): {extra[:25]}")


def licenses() -> None:
    lines = []
    for name in PYPI:
        status, _c, data, _s = fetch(f"https://pypi.org/pypi/{name}/json")
        info = data.get("info", {}) if isinstance(data, dict) else {}
        classes = [c.split("::")[-1].strip() for c in info.get("classifiers", []) if c.startswith("License")]
        lic = info.get("license_expression") or str(info.get("license") or "?")[:40]
        lines.append(f"{name}: {lic} {classes[:2]}" if status == 200 else f"{name}: HTTP {status}")
    note("notice", "Lizenzen PyPI", " | ".join(lines))
    lines = []
    for name in NPM:
        status, _c, data, _s = fetch(f"https://registry.npmjs.org/{name}/latest")
        ok = status == 200 and isinstance(data, dict)
        lines.append(f"{name} {data.get('version')}: {data.get('license')}" if ok else f"{name}: HTTP {status}")
    note("notice", "Lizenzen npm", " | ".join(lines))
    lines = []
    for repo in GITHUB:
        status, _c, data, _s = fetch(f"https://api.github.com/repos/{repo}/license")
        spdx = (data.get("license") or {}).get("spdx_id") if status == 200 and isinstance(data, dict) else None
        lines.append(f"{repo}: {spdx}" if status == 200 else f"{repo}: HTTP {status}")
    note("notice", "Lizenzen GitHub", " | ".join(lines))
    note("notice", "Nicht prüfbar hier",
         "Chromium, Firefox, WebKit und Inno Setup haben keine einheitliche Lizenzabfrage: bleiben (verify)")


MODES = {"rdap": rdap, "psi": psi, "safebrowsing": safebrowsing, "fingerprints": fingerprints, "bots": bots,
         "licenses": licenses}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in (MODES if mode == "all" else [mode]):
        try:
            MODES[name]()
        except Exception as exc:  # noqa: BLE001 – eine Messung darf die anderen nicht stoppen
            note("error", f"Messung {name}", f"{type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
