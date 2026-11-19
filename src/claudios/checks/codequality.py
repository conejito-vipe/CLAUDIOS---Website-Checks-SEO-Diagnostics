"""Code-Qualität und JavaScript-Muster. Quellen: HTML-Snapshot und die Probe 'assets' (abgerufene Stile/Skripte)."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from publicsuffix2 import get_sld

from ..core.redact import SECRET_PATTERNS, mask_secret
from ..core.registry import check
from ._util import CheckSkipped, F, S

OWASP_DOM = "https://owasp.org/www-community/attacks/DOM_Based_XSS"
MDN_SRI = "https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity"
_JS = (
    ("eval()", re.compile(r"(?<![\w.$])eval\s*\("), S.WARNING),
    ("new Function()", re.compile(r"new\s+Function\s*\("), S.WARNING),
    ("document.write()", re.compile(r"document\.write(?:ln)?\s*\("), S.WARNING),
    ("innerHTML/outerHTML", re.compile(r"\.(?:inner|outer)HTML\s*\+?="), S.NOTE),
    ("setTimeout/setInterval mit Text", re.compile(r"set(?:Timeout|Interval)\s*\(\s*[\"']"), S.NOTE),
)
_MAP = re.compile(r"(?://|/\*)[#@]\s*sourceMappingURL=([^\s*]+)")
_NO_SRI_HOSTS = {"fonts.googleapis.com"}  # dynamisch erzeugtes CSS kann keine feste Prüfsumme haben


def _assets(snap) -> dict:
    data = snap.extra.get("assets")
    if data is None:
        raise CheckSkipped("no_asset_data")
    return data


def _js_sources(snap, data) -> list[tuple[str, str]]:
    out = [(a["url"], a["text"]) for a in data["js"] if a["status"] == 200 and a["text"]]
    for pg in snap.docs():
        for script in pg.soup.find_all("script"):
            if script.get("src") or "json" in str(script.get("type", "")).lower():
                continue
            body = script.string or script.get_text()
            if body and body.strip():
                out.append((pg.url, body))
    return out


def _css_sources(snap, data) -> list[tuple[str, str]]:
    out = [(a["url"], a["text"]) for a in data["css"] if a["status"] == 200 and a["text"]]
    for pg in snap.docs():
        for style in pg.soup.find_all("style"):
            body = style.string or style.get_text()
            if body and body.strip():
                out.append((pg.url, body))
    return out


def _external(snap, url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return bool(host) and host != snap.target.host and (get_sld(host) or host) != snap.target.registrable


@check("JSS-PAT-001",
       title="Riskante JavaScript-Muster ## Risky JavaScript patterns",
       why="Funktionen wie eval(), new Function() und document.write() führen Text als Code aus oder schreiben "
           "ihn ungeprüft ins Dokument, und innerHTML ist eine häufige Quelle für Cross-Site-Scripting. Sie "
           "erschweren außerdem eine strenge Content-Security-Policy. ## Functions such as eval(), new "
           "Function() and document.write() execute text as code or write it unchecked into the document, and "
           "innerHTML is a common source of cross-site scripting. They also make a strict Content-Security-Policy "
           "harder.",
       method="Reine Textsuche in den abgerufenen eigenen Skripten (höchstens 10) und in Inline-Skripten nach "
              "eval, new Function, document.write, innerHTML/outerHTML und setTimeout mit Text sowie nach "
              "javascript:-Links im HTML. Minifizierte Fremdbibliotheken lösen die Suche oft aus, daher ist sie "
              "ein Hinweis und kein Beweis. ## Plain text search in the fetched own scripts (at most 10) and in "
              "inline scripts for eval, new Function, document.write, innerHTML/outerHTML and setTimeout with "
              "text, as well as for javascript: links in the HTML. Minified third-party libraries often trigger "
              "the search, so it is a hint and not proof.",
       logic="eval, new Function, document.write: Warnung. innerHTML, Text-Timer, javascript:-Links: Hinweis. ## "
             "eval, new Function, document.write: warning. innerHTML, text timers, javascript: links: note.",
       fix="Statt eval und innerHTML textContent, DOM-Methoden oder geprüfte Vorlagen verwenden. ## Use "
           "textContent, DOM methods or vetted templates instead of eval and innerHTML.",
       refs=[OWASP_DOM, "https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html"],
       profiles="sd", source="network")
def js_patterns(snap):
    data = _assets(snap)
    out = []
    for url, body in _js_sources(snap, data):
        for label, rx, severity in _JS:
            count = len(rx.findall(body))
            if count:
                out.append(F("JSS-PAT-001", severity, url, f"Riskantes JavaScript-Muster: {label}",
                             f"Risky JavaScript pattern: {label}", f"{count}x"))
    for pg in snap.docs():
        bad = [a for a in pg.soup.find_all("a", href=True) if str(a["href"]).strip().lower().startswith("javascript:")]
        if bad:
            out.append(F("JSS-PAT-001", S.NOTE, pg.url, f"{len(bad)} Link(s) mit javascript:-Adresse",
                         f"{len(bad)} link(s) with a javascript: address"))
    return out


@check("JSS-SRI-001",
       title="Externe Skripte ohne Subresource Integrity ## External scripts without Subresource Integrity",
       why="Wird ein Skript von einem fremden Server geladen, läuft es mit allen Rechten Ihrer Seite. Wird dieser "
           "Server gehackt, gelangt Schadcode auf Ihre Seite. Subresource Integrity (integrity-Attribut) lässt "
           "den Browser nur die erwartete Datei ausführen. ## A script loaded from a foreign server runs with "
           "all rights of your page. If that server is hacked, malicious code reaches your page. Subresource "
           "Integrity (integrity attribute) lets the browser run only the expected file.",
       method="Sucht in allen gecrawlten Seiten script- und stylesheet-Elemente mit Adresse einer anderen Domain "
              "und prüft das integrity-Attribut. Google Fonts ist ausgenommen, weil dynamisches CSS keine feste "
              "Prüfsumme haben kann. ## Looks in all crawled pages for script and stylesheet elements with an "
              "address of another domain and checks the integrity attribute. Google Fonts is excluded because "
              "dynamic CSS cannot have a fixed checksum.",
       logic="Fremdes Skript ohne integrity: Warnung. Fremdes Stylesheet ohne integrity: Hinweis. ## Foreign script "
             "without integrity: warning. Foreign stylesheet without integrity: note.",
       fix="integrity=\"sha384-...\" und crossorigin=\"anonymous\" ergänzen oder die Datei selbst hosten. ## Add "
           "integrity=\"sha384-...\" and crossorigin=\"anonymous\" or host the file yourself.",
       refs=[MDN_SRI, "https://www.w3.org/TR/SRI/"])
def sri(snap):
    out = []
    kinds = (("script", "src", S.WARNING, "Skript", "script"), ("link", "href", S.NOTE, "Stylesheet", "stylesheet"))
    for pg in snap.docs():
        for tag, attr, severity, de, en in kinds:
            for el in pg.soup.find_all(tag):
                if tag == "link" and "stylesheet" not in [r.lower() for r in (el.get("rel") or [])]:
                    continue
                value = str(el.get(attr, "")).strip()
                if not value:
                    continue
                url = urljoin(pg.url, value)
                host = (urlsplit(url).hostname or "").lower()
                if not _external(snap, url) or host in _NO_SRI_HOSTS or el.get("integrity"):
                    continue
                out.append(F("JSS-SRI-001", severity, pg.url, f"Externes {de} von {host} ohne Subresource Integrity",
                             f"External {en} from {host} without Subresource Integrity", url[:120]))
    return out


@check("JSS-MAP-001",
       title="Verweise auf Source-Maps ## References to source maps",
       why="Source-Maps enthalten den lesbaren Originalcode. Sind sie öffentlich abrufbar, erleichtert das die "
           "Suche nach Schwachstellen und legt interne Pfade und Kommentare offen. ## Source maps contain the "
           "readable original code. If they are publicly reachable, this makes it easier to look for "
           "vulnerabilities and exposes internal paths and comments.",
       method="Sucht in den abgerufenen Skripten und Stylesheets nach sourceMappingURL-Kommentaren. Ob die "
              "Map-Datei öffentlich abrufbar ist, wird nicht geprüft. ## Looks in the fetched scripts and "
              "stylesheets for sourceMappingURL comments. Whether the map file is publicly reachable is not "
              "checked.",
       logic="Verweis gefunden: Hinweis. ## Reference found: note.",
       fix="Source-Maps nur in der Entwicklung erzeugen oder den Zugriff auf .map-Dateien sperren. ## Create source "
           "maps only in development or block access to .map files.",
       refs=["https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/CSP",
             "https://sourcemaps.info/spec.html"], profiles="sd", source="network")
def source_maps(snap):
    data = _assets(snap)
    out = []
    for url, body in _js_sources(snap, data) + _css_sources(snap, data):
        match = _MAP.search(body)
        if match and url not in {f.url for f in out}:
            target = "inline (data:)" if match.group(1).startswith("data:") else match.group(1)
            out.append(F("JSS-MAP-001", S.NOTE, url, "Verweis auf eine Source-Map im ausgelieferten Code",
                         "Reference to a source map in the delivered code", target[:80]))
    return out


@check("CSS-IMP-001",
       title="CSS-Qualität (@import, !important) ## CSS quality (@import, !important)",
       why="@import lädt Stylesheets nacheinander und verzögert das Rendern. Viele !important-Angaben zeigen "
           "überladene Spezifität und machen Änderungen schwer. ## @import loads stylesheets one after another "
           "and delays rendering. Many !important declarations indicate overloaded specificity and make changes "
           "hard.",
       method="Zählt in den abgerufenen eigenen Stylesheets und in style-Elementen die Vorkommen von @import und "
              "!important. ## Counts occurrences of @import and !important in the fetched own stylesheets and in "
              "style elements.",
       logic="@import: Hinweis. Mehr als 20 !important je Datei: Hinweis. ## @import: note. More than 20 "
             "!important per file: note.",
       fix="Stylesheets per link-Element einbinden und die Spezifität der Selektoren statt !important anpassen. ## "
           "Include stylesheets via link elements and adjust selector specificity instead of !important.",
       refs=["https://developer.mozilla.org/en-US/docs/Web/CSS/@import",
             "https://developer.mozilla.org/en-US/docs/Web/CSS/important"], profiles="sd", source="network")
def css_quality(snap):
    data = _assets(snap)
    out = []
    for url, body in _css_sources(snap, data):
        if re.search(r"@import\b", body):
            out.append(F("CSS-IMP-001", S.NOTE, url, "@import im CSS (verzögert das Rendern)",
                         "@import in CSS (delays rendering)"))
        important = len(re.findall(r"!\s*important", body, re.I))
        if important > 20:
            out.append(F("CSS-IMP-001", S.NOTE, url, "Sehr viele !important-Angaben", "Very many !important declarations",
                         f"{important}x"))
    return out


@check("HTM-INL-001",
       title="Inline-Event-Handler und Inline-Styles ## Inline event handlers and inline styles",
       why="Inline-Handler wie onclick verhindern eine strenge Content-Security-Policy ohne 'unsafe-inline'. "
           "Viele Inline-Styles machen das Design schwer wartbar. ## Inline handlers such as onclick prevent a "
           "strict Content-Security-Policy without 'unsafe-inline'. Many inline styles make the design hard to "
           "maintain.",
       method="Zählt je Seite Elemente mit on…-Attributen und mit style-Attribut. ## Counts per page elements "
              "with on… attributes and with a style attribute.",
       logic="Mindestens ein Event-Handler: Hinweis. Mehr als 10 Inline-Styles: Info. ## At least one event "
             "handler: note. More than 10 inline styles: info.",
       fix="Event-Handler per addEventListener in einer Skriptdatei setzen und Stile in Stylesheets auslagern. ## Set "
           "event handlers via addEventListener in a script file and move styles into stylesheets.",
       refs=["https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP#unsafe_inline_script",
             "https://html.spec.whatwg.org/multipage/webappapis.html#event-handler-attributes"])
def inline_code(snap):
    out = []
    for pg in snap.docs():
        handlers = styles = 0
        for el in pg.soup.find_all(True):
            if el.get("style"):
                styles += 1
            if any(str(a).lower().startswith("on") and str(a).isalpha() and len(str(a)) > 2 for a in el.attrs):
                handlers += 1
        if handlers:
            out.append(F("HTM-INL-001", S.NOTE, pg.url, f"{handlers} Element(e) mit Inline-Event-Handler",
                         f"{handlers} element(s) with inline event handler"))
        if styles > 10:
            out.append(F("HTM-INL-001", S.INFO, pg.url, f"{styles} Element(e) mit Inline-Style",
                         f"{styles} element(s) with inline style"))
    return out


@check("SEC-SEC-002",
       title="Geheimnisse in JavaScript-Dateien ## Secrets in JavaScript files",
       why="Schlüssel und Tokens in ausgelieferten Skripten kann jeder Besucher lesen. Das ist ein häufiger Fehler "
           "mit hohem Schaden. ## Keys and tokens in delivered scripts can be read by every visitor. A common "
           "mistake with high impact.",
       method="Mustersuche in den abgerufenen eigenen Skripten nach bekannten Schlüsselformaten. Im Bericht "
              "erscheinen Funde nur maskiert (erste 4 Zeichen und Länge). In Bibliotheken sind Fehlalarme möglich. ## "
              "Pattern search in the fetched own scripts for known key formats. The report shows findings only "
              "masked (first 4 characters and length). False positives are possible in libraries.",
       logic="Privater Schlüssel: kritisch, sonst Fehler. ## Private key: critical, otherwise error.",
       fix="Schlüssel sofort widerrufen und erneuern und nur serverseitig verwenden. ## Revoke and rotate the key "
           "immediately and use it only server-side.",
       refs=["https://owasp.org/Top10/A02_2021-Cryptographic_Failures/", "https://cwe.mitre.org/data/definitions/798.html"],
       profiles="sd", source="network")
def secrets_in_js(snap):
    data = _assets(snap)
    out = []
    for asset in data["js"]:
        if asset["status"] != 200 or not asset["text"]:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            for match in list(pattern.finditer(asset["text"]))[:3]:
                severity = S.CRITICAL if name == "private_key" else S.ERROR
                out.append(F("SEC-SEC-002", severity, asset["url"], f"Mögliches Geheimnis in JavaScript ({name})",
                             f"Possible secret in JavaScript ({name})", mask_secret(match.group(0))))
    return out