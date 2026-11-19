"""Browser-Prüfungen (Chromium über Playwright). Die Daten liefert ein einziger Browser-Lauf pro Scan
(checks/_browser.py). Fehlt das Werkzeug oder schlägt der Lauf fehl, gilt jede Prüfung als nicht ausgeführt."""
from __future__ import annotations

import re

from ..core.numfmt import format_number
from ..core.redact import redact_url
from ..core.registry import check
from ._browser import browser_data
from ._util import CheckSkipped, F, S
from .privacy import CAT_DE, CAT_EN, detect_services, service_of

NEEDS = ("node", "playwright")
WCAG = "https://www.w3.org/WAI/WCAG22/quickref/"
PLAYWRIGHT = "https://playwright.dev/"
_IMPACT = {"critical": S.ERROR, "serious": S.WARNING, "moderate": S.NOTE, "minor": S.INFO}
_TRACKERS = re.compile(r"^(_ga(_.*)?|_gid|_gat.*|_gcl_.*|_fbp|_fbc|_hj.*|_clck|_clsk|_uetsid|_uetvid|_pk_.*|ajs_.*)$",
                       re.I)


def _pages(snap) -> list[dict]:
    return [p for p in browser_data(snap)["pages"] if isinstance(p, dict)]


@check("BRW-CON-001",
       title="Konsolenfehler und fehlgeschlagene Ressourcen im Browser ## Console errors and failed resources in the browser",
       why="JavaScript-Ausnahmen brechen Funktionen oft unbemerkt ab, und fehlende Dateien (404) lassen Seiten "
           "kaputt aussehen. Beides zeigt sich nur, wenn die Seite wirklich in einem Browser läuft, nicht im "
           "reinen HTML. ## JavaScript exceptions often break features unnoticed, and missing files (404) make "
           "pages look broken. Both only show when the page really runs in a browser, not in the plain HTML.",
       method="Lädt eine Stichprobe der gecrawlten Seiten (Standard 10, Tief 25) in Chromium (Playwright, ein "
              "Lauf für alle Browser-Prüfungen) und sammelt Konsolenfehler, JavaScript-Ausnahmen, fehlgeschlagene "
              "Anfragen und HTTP-Fehler. Der Browser verbindet direkt und nicht über den Gatekeeper, er lädt "
              "wie ein Besucher alle Ressourcen der Seite; zwischen den Seiten liegen 700 ms. Der Zielhost ist auf "
              "die zuvor geprüfte öffentliche IP festgelegt, Anfragen über HTTP oder an lokale Adressen werden "
              "abgebrochen, Zertifikatsfehler nie ignoriert. Bei fehlendem Werkzeug oder Fehlschlag gilt die "
              "Prüfung als nicht ausgeführt. ## Loads a sample of the crawled pages (standard 10, deep 25) in "
              "Chromium (Playwright, one run for all browser checks) and collects console errors, JavaScript "
              "exceptions, failed requests and HTTP errors. The browser connects directly and not through the "
              "gatekeeper, it loads all resources of the page like a visitor; 700 ms lie between pages. The "
              "target host is pinned to the previously verified public IP, requests over HTTP or to local "
              "addresses are aborted, certificate errors are never ignored. With a missing tool or a failure "
              "the check counts as not executed.",
       logic="JavaScript-Ausnahme, HTTP 404 oder 5xx, Seite nicht ladbar, HTTP-Anfrage: Warnung. Konsolenfehler, "
             "andere Ressourcenfehler: Hinweis. ## JavaScript exception, HTTP 404 or 5xx, page not loadable, HTTP "
             "request: warning. Console errors, other resource errors: note.",
       fix="Die Meldung im Beleg in den Entwicklerwerkzeugen des Browsers (F12, Konsole und Netzwerk) nachstellen "
           "und beheben. ## Reproduce the message from the evidence in the browser developer tools (F12, console "
           "and network) and fix it.",
       refs=["https://developer.mozilla.org/en-US/docs/Web/API/console", PLAYWRIGHT],
       profiles="sd", source="tool", needs=NEEDS)
def console_errors(snap):
    out = []
    for p in _pages(snap):
        url = p.get("url", snap.target.url)
        error = p.get("error")
        if error:
            if error != "offsite_redirect":
                out.append(F("BRW-CON-001", S.WARNING, url, "Die Seite konnte im Browser nicht geladen werden",
                             "The page could not be loaded in the browser", str(error)[:80]))
            continue
        exceptions = p.get("page_errors") or []
        if exceptions:
            out.append(F("BRW-CON-001", S.WARNING, url, f"{len(exceptions)} JavaScript-Ausnahme(n) beim Laden",
                         f"{len(exceptions)} JavaScript exception(s) while loading", str(exceptions[0])))
        errors = [m for m in p.get("console") or [] if isinstance(m, dict) and m.get("type") == "error"]
        if errors:
            out.append(F("BRW-CON-001", S.NOTE, url, f"{len(errors)} Konsolenfehler", f"{len(errors)} console error(s)",
                         str(errors[0].get("text", ""))))
        bad = [b for b in p.get("bad_status") or [] if isinstance(b, dict)]
        if bad:
            severe = any(b.get("status") == 404 or int(b.get("status", 0)) >= 500 for b in bad)
            first = bad[0]
            out.append(F("BRW-CON-001", S.WARNING if severe else S.NOTE, url,
                         f"{len(bad)} Ressource(n) mit HTTP-Fehler", f"{len(bad)} resource(s) with an HTTP error",
                         f"HTTP {first.get('status')} {redact_url(str(first.get('url', '')))}"))
        failed = [f for f in p.get("failed") or [] if isinstance(f, dict)]
        if failed:
            first = failed[0]
            out.append(F("BRW-CON-001", S.NOTE, url, f"{len(failed)} Ressource(n) konnten nicht geladen werden",
                         f"{len(failed)} resource(s) could not be loaded",
                         f"{redact_url(str(first.get('url', '')))} {first.get('reason', '')}"))
        blocked = p.get("insecure_blocked") or []
        if blocked:
            out.append(F("BRW-CON-001", S.WARNING, url,
                         "Die Seite fordert Ressourcen über unverschlüsseltes HTTP an (im Browser blockiert)",
                         "The page requests resources over unencrypted HTTP (blocked in the browser)",
                         redact_url(str(blocked[0]))))
    return out


@check("BRW-AXE-001",
       title="Barrierefreiheit im Browser (axe-core, WCAG 2.2) ## Accessibility in the browser (axe-core, WCAG 2.2)",
       why="Fehlende Alternativtexte, zu geringe Kontraste oder falsche ARIA-Angaben schließen Menschen mit "
           "Einschränkungen aus. Ein Teil davon ist rechtlich relevant, in Deutschland etwa durch das "
           "Barrierefreiheitsstärkungsgesetz. Viele Fehler lassen sich erst im gerenderten Dokument finden. ## "
           "Missing alternative texts, insufficient contrast or wrong ARIA attributes exclude people with "
           "disabilities. Part of this is legally relevant, in Germany for example through the Accessibility "
           "Strengthening Act. Many errors can only be found in the rendered document.",
       method="Führt axe-core (Regeln für WCAG 2.0 bis 2.2, Stufen A und AA) in der gerenderten Seite aus, "
              "gleiche Stichprobe wie die übrigen Browser-Prüfungen. Automatische Tests finden nur einen Teil der "
              "Probleme, Tastaturbedienung und Verständlichkeit prüft kein Werkzeug vollständig. ## Runs axe-core "
              "(rules for WCAG 2.0 to 2.2, levels A and AA) in the rendered page, same sample as the other "
              "browser checks. Automatic tests only find part of the problems, no tool fully checks keyboard "
              "operation and understandability.",
       logic="Wirkung laut axe: kritisch: Fehler, schwerwiegend: Warnung, mittel: Hinweis, gering: Info. Je Regel "
             "und Seite ein Befund. ## Impact according to axe: critical: error, serious: warning, moderate: "
             "note, minor: info. One finding per rule and page.",
       fix="Die im Beleg verlinkte axe-Erklärung zur Regel lesen und die genannten Elemente korrigieren. ## Read "
           "the axe explanation of the rule linked in the evidence and fix the elements named.",
       refs=[WCAG, "https://github.com/dequelabs/axe-core"],
       profiles="sd", source="tool", needs=NEEDS)
def accessibility(snap):
    pages = [p for p in _pages(snap) if not p.get("error")]
    if pages and all(p.get("axe") is None for p in pages):
        raise CheckSkipped("axe_failed")
    out = []
    for p in pages:
        url = p.get("url", snap.target.url)
        for v in p.get("axe") or []:
            if not isinstance(v, dict):
                continue
            nodes, rule, text = int(v.get("nodes", 1)), v.get("id", "?"), v.get("help", "")
            out.append(F("BRW-AXE-001", _IMPACT.get(v.get("impact"), S.NOTE), url,
                         f"Barrierefreiheit: {text} ({nodes} Element(e), Regel {rule})",
                         f"Accessibility: {text} ({nodes} element(s), rule {rule})", str(v.get("url", ""))[:120]))
    return out


@check("BRW-RSP-001",
       title="Responsive Darstellung (360, 768 und 1280 px) ## Responsive layout (360, 768 and 1280 px)",
       why="Muss man auf dem Smartphone seitlich scrollen, ist die Seite schwer lesbar und bedienbar. Google bewertet "
           "die mobile Darstellung, und WCAG verlangt, dass Inhalte ohne zweidimensionales Scrollen lesbar "
           "bleiben (Reflow). ## If you have to scroll sideways on a smartphone the page is hard to read and "
           "use. Google evaluates the mobile layout, and WCAG requires content to stay readable without "
           "two-dimensional scrolling (reflow).",
       method="Setzt im Browser nacheinander die Breiten 360, 768 und 1280 px und prüft, ob die Seite breiter ist "
              "als das Fenster (horizontales Scrollen). Gleiche Stichprobe wie die übrigen Browser-Prüfungen. ## "
              "Sets the widths 360, 768 and 1280 px one after another in the browser and checks whether the page "
              "is wider than the window (horizontal scrolling). Same sample as the other browser checks.",
       logic="Überlauf bei 360 px: Warnung. Nur bei 768 oder 1280 px: Hinweis. ## Overflow at 360 px: warning. Only "
             "at 768 or 1280 px: note.",
       fix="Feste Breiten durch flexible ersetzen (max-width, Flexbox, Grid), Bilder mit max-width: 100% begrenzen "
           "und das viewport-Meta setzen. ## Replace fixed widths with flexible ones (max-width, flexbox, grid), "
           "limit images with max-width: 100% and set the viewport meta.",
       refs=["https://www.w3.org/TR/WCAG22/#reflow", PLAYWRIGHT],
       profiles="sd", source="tool", needs=NEEDS)
def responsive(snap):
    out = []
    for p in _pages(snap):
        if p.get("error"):
            continue
        url = p.get("url", snap.target.url)
        overflow = p.get("overflow") or {}
        for width in (360, 768, 1280):
            if overflow.get(str(width)) is True:
                out.append(F("BRW-RSP-001", S.WARNING if width == 360 else S.NOTE, url,
                             f"Horizontales Scrollen in der {width}px-Ansicht",
                             f"Horizontal scrolling in the {width}px view"))
    return out


@check("BRW-PRF-001",
       title="Ladeleistung im Browser (Labormessung) ## Loading performance in the browser (lab measurement)",
       why="Langsam ladende oder springende Seiten verlieren Besucher und werden von Google schlechter bewertet "
           "(Core Web Vitals). Der größte sichtbare Inhalt (LCP) und die Layout-Verschiebung (CLS) messen, wie "
           "schnell und stabil sich die Seite aufbaut. ## Slow or jumping pages lose visitors and are rated "
           "worse by Google (Core Web Vitals). The largest visible content (LCP) and the layout shift (CLS) "
           "measure how fast and stable the page builds up.",
       method="Misst im Browser LCP und CLS über PerformanceObserver, zählt die Anfragen und schätzt das Gewicht aus "
              "den Content-Length-Angaben (komprimierte Größe, ohne Angabe ungezählt). Das ist eine Labormessung "
              "ohne Drosselung auf einem Rechner mit anderer Leistung, nicht die Praxisdaten von Besuchern. "
              "Gleiche Stichprobe wie die übrigen Browser-Prüfungen. ## Measures LCP and CLS in the browser via "
              "PerformanceObserver, counts the requests and estimates the weight from the Content-Length values "
              "(compressed size, uncounted without a value). This is a lab measurement without throttling on a "
              "machine with different performance, not real-world data of visitors. Same sample as the other "
              "browser checks.",
       logic="LCP über 4000 ms oder CLS über 0,25: Warnung. LCP über 2500 ms, CLS über 0,1, über 150 Anfragen oder "
             "über 3 MB: Hinweis. ## LCP above 4000 ms or CLS above 0.25: warning. LCP above 2500 ms, CLS above "
             "0.1, above 150 requests or above 3 MB: note.",
       fix="Bilder verkleinern und mit Breite und Höhe versehen, Skripte aufschieben, Schriften vorladen, "
           "Komprimierung und Caching aktivieren. ## Shrink images and give them width and height, defer scripts, "
           "preload fonts, enable compression and caching.",
       refs=["https://web.dev/articles/vitals", PLAYWRIGHT],
       profiles="sd", source="tool", needs=NEEDS)
def performance(snap):
    out = []
    for p in _pages(snap):
        if p.get("error"):
            continue
        url, m = p.get("url", snap.target.url), p.get("metrics") or {}
        lcp, cls = m.get("lcp") or 0, m.get("cls") or 0
        if lcp > 4000:
            out.append(F("BRW-PRF-001", S.WARNING, url, f"Der größte sichtbare Inhalt (LCP) erscheint erst nach {lcp} ms",
                         f"The largest visible content (LCP) appears only after {lcp} ms"))
        elif lcp > 2500:
            out.append(F("BRW-PRF-001", S.NOTE, url, f"Der größte sichtbare Inhalt (LCP) erscheint nach {lcp} ms",
                         f"The largest visible content (LCP) appears after {lcp} ms"))
        if cls > 0.1:
            out.append(F("BRW-PRF-001", S.WARNING if cls > 0.25 else S.NOTE, url,
                         f"Layout-Verschiebung (CLS) {format_number(cls, 'de', 2)}",
                         f"Layout shift (CLS) {format_number(cls, 'en', 2)}"))
        if (m.get("requests") or 0) > 150:
            out.append(F("BRW-PRF-001", S.NOTE, url, f"{m['requests']} Anfragen beim Laden der Seite",
                         f"{m['requests']} requests while loading the page"))
        if (m.get("bytes") or 0) > 3_000_000:
            out.append(F("BRW-PRF-001", S.NOTE, url, "Das Seitengewicht liegt über 3 MB (geschätzt, komprimiert)",
                         "The page weight is above 3 MB (estimated, compressed)"))
    return out


@check("PRV-BRW-001",
       title="Nachgeladene Dienste und Cookies vor der Einwilligung ## Services and cookies loaded later, before consent",
       why="Viele Tracker und Fremddienste werden erst per JavaScript nachgeladen und fehlen deshalb im reinen "
           "HTML. Sie übertragen Daten und setzen Cookies, bevor ein Besucher etwas entscheiden konnte. In der "
           "Regel braucht das eine Einwilligung. ## Many trackers and third-party services are only loaded by "
           "JavaScript and are therefore missing in the plain HTML. They transmit data and set cookies before a "
           "visitor could decide anything. This usually requires consent.",
       method="Lädt die Seite im Browser, ohne etwas anzuklicken, und wertet die kontaktierten Fremd-Hosts und die "
              "gesetzten Cookies aus (nur Namen, nie Werte). Dienste, die schon im HTML gefunden wurden, und "
              "Cookies aus Antwort-Headern werden nicht doppelt gemeldet. Technischer Hinweis, keine "
              "Rechtsberatung; ob eine Einwilligung nötig ist, hängt vom Einzelfall ab. ## Loads the page in the "
              "browser without clicking anything and evaluates the third-party hosts contacted and the cookies "
              "set (names only, never values). Services already found in the HTML and cookies from response "
              "headers are not reported twice. Technical indication, not legal advice; whether consent is needed "
              "depends on the case.",
       logic="Tracking-Dienst oder bekanntes Tracking-Cookie: Warnung. Schriften, Video, Karten, soziale Netzwerke, "
             "CAPTCHA: Hinweis. Unbekannte Fremd-Hosts: Info. ## Tracking service or known tracking cookie: "
             "warning. Fonts, video, maps, social networks, CAPTCHA: note. Unknown third-party hosts: info.",
       fix="Dienste und Cookies erst nach aktiver Einwilligung laden und setzen; eine Einwilligungslösung einsetzen, "
           "die Skripte bis dahin blockiert. ## Load services and set cookies only after active consent; use a "
           "consent solution that blocks scripts until then.",
       refs=["https://eur-lex.europa.eu/eli/reg/2016/679/oj", "https://eur-lex.europa.eu/eli/dir/2002/58/oj"],
       profiles="sd", source="tool", needs=NEEDS)
def dynamic_privacy(snap):
    html_services = set(detect_services(snap))
    header_cookies = {c.name for pg in snap.pages for c in pg.cookies}
    out, seen_services, seen_cookies, unknown = [], set(), set(), {}
    for p in _pages(snap):
        if p.get("error"):
            continue
        url = p.get("url", snap.target.url)
        for host in sorted(p.get("third_party") or {}):
            hit = service_of(f"https://{host}/")
            if hit is None:
                unknown.setdefault(host, url)
                continue
            name, category = hit
            if name in html_services or name in seen_services:
                continue
            seen_services.add(name)
            out.append(F("PRV-BRW-001", S.WARNING if category == "tracking" else S.NOTE, url,
                         f"Im Browser nachgeladener Dienst: {name} ({CAT_DE[category]})",
                         f"Service loaded later in the browser: {name} ({CAT_EN[category]})", name))
        for cookie in p.get("cookies") or []:
            name = str(cookie.get("name", "")) if isinstance(cookie, dict) else ""
            if name and name not in header_cookies and name not in seen_cookies and _TRACKERS.match(name):
                seen_cookies.add(name)
                out.append(F("PRV-BRW-001", S.WARNING, url,
                             f"Tracking-Cookie nach dem Laden gesetzt, ohne Einwilligung: {name}",
                             f"Tracking cookie set after loading, without consent: {name}", name))
    if unknown:
        first = sorted(unknown)
        out.append(F("PRV-BRW-001", S.INFO, unknown[first[0]],
                     f"{len(unknown)} weitere Fremd-Host(s) beim Laden kontaktiert",
                     f"{len(unknown)} more third-party host(s) contacted while loading", ", ".join(first[:5])))
    return out
