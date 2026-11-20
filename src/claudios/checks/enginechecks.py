"""Browser-Vergleich: Unterschiede zwischen Chromium und Firefox/WebKit (Daten aus core/probe_engines.py, nur im
Profil Tief). Der Vergleich nutzt die Daten des Chromium-Laufs (checks/_browser.py), soweit vorhanden."""
from __future__ import annotations

from ..core.registry import check
from ._browser import browser_data
from ._util import CheckSkipped, F, S

NEEDS = ("node", "playwright", "pw-browsers")
LABEL = {"firefox": "Firefox", "webkit": "WebKit"}


def _baseline(snap) -> dict[str, dict]:
    try:
        data = browser_data(snap)
    except CheckSkipped:
        return {}
    return {str(p.get("url")): p for p in data.get("pages") or [] if isinstance(p, dict)}


@check("BRW-ENG-001",
       title="Browser-Unterschiede (Firefox und WebKit) ## Browser differences (Firefox and WebKit)",
       why="Eine Website, die nur in Chromium getestet wurde, kann in Firefox oder Safari (WebKit) kaputt aussehen oder "
           "gar nicht laden. Ein erheblicher Teil der Besucher nutzt diese Browser. ## A website tested only in "
           "Chromium can look broken or fail to load in Firefox or Safari (WebKit). A considerable part of the visitors "
           "uses these browsers.",
       method="Nur im Profil Tief und nur mit installierter Komponente Firefox und WebKit. Lädt bis zu 3 Seiten in beiden "
              "Browsern (Playwright, ein Lauf) und vergleicht mit dem Chromium-Lauf: Ladefehler, JavaScript-Ausnahmen und "
              "horizontales Scrollen bei 360 px. Anders als bei Chromium ist der Zielhost nicht an die geprüfte IP "
              "festgelegt: CLAUDIOS prüft die Auflösung vor und nach dem Lauf und verwirft Daten auffälliger Fremd-Hosts. "
              "WebKit unter Windows ist nicht Safari, sondern die Engine in Playwright. ## Only in the deep profile and only "
              "with the Firefox and WebKit component installed. Loads up to 3 pages in both browsers (Playwright, one "
              "run) and compares with the Chromium run: load errors, JavaScript exceptions and horizontal scrolling at "
              "360 px. Unlike Chromium the target host is not pinned to the verified IP: CLAUDIOS checks the resolution "
              "before and after the run and discards data of suspicious third-party hosts. WebKit on Windows is not "
              "Safari but the engine shipped with Playwright.",
       logic="Seite lädt nur in diesem Browser nicht: Warnung. Neue JavaScript-Ausnahmen oder Überlauf bei 360 px nur "
             "hier: Hinweis. Browser startet nicht: Info. ## Page fails to load only in this browser: warning. New "
             "JavaScript exceptions or overflow at 360 px only here: note. Browser does not start: info.",
       fix="Die Seite in Firefox und im WebKit-Browser öffnen (Entwicklerwerkzeuge, Konsole) und die Abweichung beheben, "
           "zum Beispiel fehlende Präfixe oder nicht unterstützte Funktionen ersetzen. ## Open the page in Firefox and in "
           "the WebKit browser (developer tools, console) and fix the difference, for example replace missing prefixes or "
           "unsupported features.",
       refs=["https://playwright.dev/docs/browsers", "https://caniuse.com/"],
       profiles="d", source="tool", needs=NEEDS)
def engine_differences(snap):
    data = snap.extra.get("engines")
    if data is None:
        raise CheckSkipped("no_engine_data")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    engines = [e for e in data.get("engines") or [] if isinstance(e, dict)]
    if not engines or all(e.get("error") and not e.get("pages") for e in engines):
        raise CheckSkipped("engines_failed")
    base = _baseline(snap)
    out = []
    for eng in engines:
        label = LABEL.get(eng.get("engine"), str(eng.get("engine"))[:20])
        if eng.get("error") and not eng.get("pages"):
            out.append(F("BRW-ENG-001", S.INFO, snap.target.url, f"{label} konnte nicht gestartet werden",
                         f"{label} could not be started", str(eng["error"])[:80]))
            continue
        for page in eng.get("pages") or []:
            if not isinstance(page, dict):
                continue
            url = str(page.get("url", snap.target.url))
            ref = base.get(url, {})
            ref_ok = bool(ref) and not ref.get("error")
            error = page.get("error")
            if error:
                if error != "offsite_redirect":
                    out.append(F("BRW-ENG-001", S.WARNING if ref_ok else S.NOTE, url,
                                 f"Die Seite konnte in {label} nicht geladen werden"
                                 + (" (in Chromium schon)" if ref_ok else ""),
                                 f"The page could not be loaded in {label}" + (" (it loads in Chromium)" if ref_ok else ""),
                                 str(error)[:80]))
                continue
            errors = page.get("page_errors") or []
            if errors and ref and not ref.get("page_errors"):
                out.append(F("BRW-ENG-001", S.NOTE, url, f"{len(errors)} JavaScript-Ausnahme(n) nur in {label}",
                             f"{len(errors)} JavaScript exception(s) only in {label}", str(errors[0])[:100]))
            overflow = page.get("overflow") or {}
            if overflow.get("360") is True and ref and not (ref.get("overflow") or {}).get("360"):
                out.append(F("BRW-ENG-001", S.NOTE, url, f"Horizontales Scrollen bei 360 px nur in {label}",
                             f"Horizontal scrolling at 360 px only in {label}"))
    return out
