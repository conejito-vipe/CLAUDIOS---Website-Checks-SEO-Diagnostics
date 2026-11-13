from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from ..core.redact import SECRET_PATTERNS, mask_secret
from ..core.registry import check
from ._util import F, S

OWASP = "https://owasp.org/www-project-secure-headers/"
MDN = "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/"


def _csp(value: str) -> dict[str, list[str]]:
    d: dict[str, list[str]] = {}
    for part in value.split(";"):
        bits = part.strip().split()
        if bits:
            d.setdefault(bits[0].lower(), [b.lower() for b in bits[1:]])
    return d


@check("SEC-HDR-001",
       title="Content-Security-Policy ## Content-Security-Policy",
       why="Die CSP begrenzt, welche Skripte und Quellen eine Seite laden darf, und ist die wirksamste Bremse "
           "gegen Cross-Site-Scripting. ## The CSP limits which scripts and sources a page may load and is the "
           "most effective brake on cross-site scripting.",
       method="Liest den Header je Seite und zerlegt die Direktiven; prüft script-src (bzw. default-src) auf "
              "'unsafe-inline' ohne Nonce/Hash, 'unsafe-eval' und breite Quellen (*, http:, https:, data:). ## "
              "Reads the header per page and parses directives; checks script-src (or default-src) for "
              "'unsafe-inline' without nonce/hash, 'unsafe-eval' and broad sources (*, http:, https:, data:).",
       logic="Fehlt: Warnung. Unsichere Quellen: Warnung. Keine script-Direktive: Hinweis. ## "
             "Missing: warning. Unsafe sources: warning. No script directive: note.",
       fix="Header Content-Security-Policy setzen, Nonces oder Hashes statt 'unsafe-inline' verwenden. ## "
           "Set a Content-Security-Policy header, use nonces or hashes instead of 'unsafe-inline'.",
       refs=["https://www.w3.org/TR/CSP3/", MDN + "Content-Security-Policy", OWASP])
def csp(snap):
    out = []
    for pg in snap.docs():
        v = pg.headers.get("content-security-policy")
        if not v:
            out.append(F("SEC-HDR-001", S.WARNING, pg.url, "Keine Content-Security-Policy", "No Content-Security-Policy"))
            continue
        d = _csp(v)
        if "script-src" not in d and "default-src" not in d:
            out.append(F("SEC-HDR-001", S.NOTE, pg.url, "CSP ohne script-src/default-src", "CSP without script-src/default-src"))
            continue
        script = d.get("script-src", d.get("default-src", []))
        if "'unsafe-inline'" in script and not any(t.startswith(("'nonce-", "'sha")) for t in script):
            out.append(F("SEC-HDR-001", S.WARNING, pg.url, "CSP erlaubt 'unsafe-inline' für Skripte", "CSP allows 'unsafe-inline' for scripts"))
        if "'unsafe-eval'" in script:
            out.append(F("SEC-HDR-001", S.WARNING, pg.url, "CSP erlaubt 'unsafe-eval'", "CSP allows 'unsafe-eval'"))
        if "*" in script or any(t in ("http:", "https:", "data:") for t in script):
            out.append(F("SEC-HDR-001", S.WARNING, pg.url, "CSP erlaubt zu breite Skriptquellen", "CSP allows overly broad script sources"))
    return out


@check("SEC-HDR-002",
       title="HSTS (Strict-Transport-Security) ## HSTS (Strict-Transport-Security)",
       why="HSTS zwingt Browser dauerhaft zu HTTPS und verhindert Downgrade- und Mitlese-Angriffe beim "
           "ersten Aufruf. ## HSTS forces browsers to HTTPS permanently and prevents downgrade and "
           "eavesdropping attacks on the first request.",
       method="Liest Strict-Transport-Security und wertet max-age aus. ## Reads Strict-Transport-Security and evaluates max-age.",
       logic="Fehlt: Warnung. max-age unter 180 Tagen: Hinweis. ## Missing: warning. max-age below 180 days: note.",
       fix="Strict-Transport-Security: max-age=31536000; includeSubDomains setzen. ## "
           "Set Strict-Transport-Security: max-age=31536000; includeSubDomains.",
       refs=["https://www.rfc-editor.org/rfc/rfc6797", MDN + "Strict-Transport-Security"])
def hsts(snap):
    out = []
    for pg in snap.docs():
        v = pg.headers.get("strict-transport-security", "")
        m = re.search(r"max-age=(\d+)", v, re.I)
        if not m:
            out.append(F("SEC-HDR-002", S.WARNING, pg.url, "HSTS fehlt oder ist ungültig", "HSTS missing or invalid"))
        elif int(m.group(1)) < 15552000:
            out.append(F("SEC-HDR-002", S.NOTE, pg.url, "HSTS max-age unter 180 Tagen", "HSTS max-age below 180 days"))
    return out


@check("SEC-HDR-003",
       title="X-Content-Type-Options ## X-Content-Type-Options",
       why="Ohne nosniff darf der Browser Dateitypen erraten, wodurch hochgeladene Dateien als Skript "
           "ausgeführt werden könnten. ## Without nosniff the browser may guess file types, so uploaded "
           "files could be executed as script.",
       method="Prüft, ob der Header den Wert nosniff hat. ## Checks that the header has the value nosniff.",
       logic="Fehlt oder abweichend: Hinweis. ## Missing or different: note.",
       fix="X-Content-Type-Options: nosniff senden. ## Send X-Content-Type-Options: nosniff.",
       refs=[MDN + "X-Content-Type-Options", OWASP])
def nosniff(snap):
    return [F("SEC-HDR-003", S.NOTE, pg.url, "X-Content-Type-Options: nosniff fehlt", "X-Content-Type-Options: nosniff missing")
            for pg in snap.docs() if pg.headers.get("x-content-type-options", "").strip().lower() != "nosniff"]


@check("SEC-HDR-004",
       title="Clickjacking-Schutz ## Clickjacking protection",
       why="Ohne Schutz kann die Seite unsichtbar in fremde Seiten eingebettet und Nutzern untergeschoben werden. ## "
           "Without protection the page can be embedded invisibly in foreign sites to trick users.",
       method="Sucht frame-ancestors in der CSP oder X-Frame-Options (DENY/SAMEORIGIN). ## "
              "Looks for frame-ancestors in the CSP or X-Frame-Options (DENY/SAMEORIGIN).",
       logic="Keines von beiden: Warnung. ## Neither present: warning.",
       fix="Content-Security-Policy: frame-ancestors 'self' setzen. ## Set Content-Security-Policy: frame-ancestors 'self'.",
       refs=["https://www.w3.org/TR/CSP3/#directive-frame-ancestors", MDN + "X-Frame-Options"])
def clickjacking(snap):
    out = []
    for pg in snap.docs():
        has_fa = "frame-ancestors" in _csp(pg.headers.get("content-security-policy", ""))
        xfo = pg.headers.get("x-frame-options", "").strip().upper() in ("DENY", "SAMEORIGIN")
        if not (has_fa or xfo):
            out.append(F("SEC-HDR-004", S.WARNING, pg.url, "Kein Clickjacking-Schutz", "No clickjacking protection"))
    return out


@check("SEC-HDR-005",
       title="Referrer-Policy ## Referrer-Policy",
       why="Ohne Richtlinie können vollständige URLs (mit Parametern) an Drittseiten übermittelt werden. ## "
           "Without a policy full URLs (including parameters) can be sent to third-party sites.",
       method="Liest Referrer-Policy bzw. meta name=referrer. ## Reads Referrer-Policy or meta name=referrer.",
       logic="Fehlt: Info. unsafe-url/no-referrer-when-downgrade: Hinweis. ## "
             "Missing: info. unsafe-url/no-referrer-when-downgrade: note.",
       fix="Referrer-Policy: strict-origin-when-cross-origin senden. ## Send Referrer-Policy: strict-origin-when-cross-origin.",
       refs=["https://www.w3.org/TR/referrer-policy/", MDN + "Referrer-Policy"])
def referrer(snap):
    out = []
    for pg in snap.docs():
        v = pg.headers.get("referrer-policy", "").lower()
        if not v:
            meta = pg.soup.find("meta", attrs={"name": re.compile("^referrer$", re.I)})
            v = str(meta.get("content", "")).lower() if meta else ""
        if not v:
            out.append(F("SEC-HDR-005", S.INFO, pg.url, "Keine Referrer-Policy", "No Referrer-Policy"))
        elif any(x in v for x in ("unsafe-url", "no-referrer-when-downgrade")):
            out.append(F("SEC-HDR-005", S.NOTE, pg.url, "Unsichere Referrer-Policy", "Unsafe Referrer-Policy", v))
    return out


@check("SEC-HDR-006",
       title="Versionsangaben in Headern ## Version disclosure in headers",
       why="Versionsnummern in Server-Headern erleichtern gezielte Angriffe auf bekannte Schwachstellen. ## "
           "Version numbers in server headers make targeted attacks on known vulnerabilities easier.",
       method="Prüft Server, X-Powered-By, X-AspNet-Version auf Versionsnummern. ## "
              "Checks Server, X-Powered-By, X-AspNet-Version for version numbers.",
       logic="Version sichtbar: Hinweis. ## Version visible: note.",
       fix="Header entfernen oder Versionsangabe abschalten. ## Remove the header or disable the version string.",
       refs=[OWASP, "https://owasp.org/www-project-web-security-testing-guide/"])
def info_leak(snap):
    out, seen = [], set()
    for pg in snap.docs():
        for h in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"):
            v = pg.headers.get(h, "")
            if v and (h != "server" or re.search(r"\d", v)) and (h, v) not in seen:
                seen.add((h, v))
                out.append(F("SEC-HDR-006", S.NOTE, pg.url, f"Header {h} verrät Version/Technik",
                             f"Header {h} discloses version/technology", v))
    return out


@check("SEC-COK-001",
       title="Cookie-Flags ## Cookie flags",
       why="Cookies ohne Secure, HttpOnly und SameSite können abgehört, per Skript gestohlen oder "
           "für Cross-Site-Anfragen missbraucht werden. ## Cookies without Secure, HttpOnly and SameSite can "
           "be intercepted, stolen by script or abused in cross-site requests.",
       method="Wertet nur Name und Attribute der Set-Cookie-Header aus; Werte werden nie gespeichert. "
              "Prüft auch __Host-/__Secure-Präfixe und Laufzeit über 400 Tage. ## "
              "Evaluates only names and attributes of Set-Cookie headers; values are never stored. Also checks "
              "__Host-/__Secure- prefixes and lifetime above 400 days.",
       logic="Ohne Secure: Fehler. Ohne HttpOnly bei Sitzungsnamen: Warnung, sonst Hinweis. SameSite=None ohne Secure oder "
             "verletztes Präfix: Fehler. ## Without Secure: error. Without HttpOnly for session-like names: warning, "
             "otherwise note. SameSite=None without Secure or violated prefix: error.",
       fix="Set-Cookie: name=...; Secure; HttpOnly; SameSite=Lax; Path=/ ## "
           "Set-Cookie: name=...; Secure; HttpOnly; SameSite=Lax; Path=/",
       refs=["https://www.rfc-editor.org/rfc/rfc6265", "https://owasp.org/www-community/controls/SecureCookieAttribute"])
def cookies(snap):
    out, seen = [], set()
    sessionish = re.compile(r"(sess|sid|auth|token|login|jwt)", re.I)
    for pg in snap.pages:
        for c in pg.cookies:
            if c.name in seen:
                continue
            seen.add(c.name)
            u, n = pg.url, c.name
            if not c.secure:
                out.append(F("SEC-COK-001", S.ERROR, u, f"Cookie {n}: Flag Secure fehlt", f"Cookie {n}: Secure flag missing", n))
            if not c.httponly:
                sev = S.WARNING if sessionish.search(n) else S.NOTE
                out.append(F("SEC-COK-001", sev, u, f"Cookie {n}: Flag HttpOnly fehlt", f"Cookie {n}: HttpOnly flag missing", n))
            if (c.samesite or "").lower() == "none" and not c.secure:
                out.append(F("SEC-COK-001", S.ERROR, u, f"Cookie {n}: SameSite=None ohne Secure", f"Cookie {n}: SameSite=None without Secure", n))
            elif not c.samesite:
                out.append(F("SEC-COK-001", S.NOTE, u, f"Cookie {n}: SameSite nicht gesetzt", f"Cookie {n}: SameSite not set", n))
            if n.startswith("__Host-") and not (c.secure and c.path == "/" and not c.domain):
                out.append(F("SEC-COK-001", S.ERROR, u, f"Cookie {n}: __Host-Präfix verletzt", f"Cookie {n}: __Host- prefix violated", n))
            if n.startswith("__Secure-") and not c.secure:
                out.append(F("SEC-COK-001", S.ERROR, u, f"Cookie {n}: __Secure-Präfix verletzt", f"Cookie {n}: __Secure- prefix violated", n))
            if c.lifetime_days is not None and c.lifetime_days > 400:
                out.append(F("SEC-COK-001", S.NOTE, u, f"Cookie {n}: Laufzeit über 400 Tage", f"Cookie {n}: lifetime above 400 days", n))
    return out


@check("SEC-HTM-001",
       title="target=\"_blank\" ohne rel ## target=\"_blank\" without rel",
       why="Verlinkte Seiten könnten über window.opener die Ursprungsseite umleiten (Tabnabbing). Moderne Browser "
           "mildern das, ältere nicht. ## Linked pages could redirect the origin page via window.opener "
           "(tabnabbing). Modern browsers mitigate it, older ones do not.",
       method="Sucht a[target=_blank] ohne rel=noopener oder noreferrer. ## Looks for a[target=_blank] without rel=noopener or noreferrer.",
       logic="Hinweis je Seite. ## Note per page.",
       fix="rel=\"noopener noreferrer\" ergänzen. ## Add rel=\"noopener noreferrer\".",
       refs=["https://html.spec.whatwg.org/multipage/links.html#link-type-noopener", "https://owasp.org/www-community/attacks/Reverse_Tabnabbing"])
def target_blank(snap):
    out = []
    for pg in snap.docs():
        bad = [a for a in pg.soup.find_all("a", target="_blank")
               if not {"noopener", "noreferrer"} & set(a.get("rel") or [])]
        if bad:
            out.append(F("SEC-HTM-001", S.NOTE, pg.url, f"{len(bad)} Link(s) mit target=_blank ohne noopener",
                         f"{len(bad)} link(s) with target=_blank without noopener", str(bad[0].get("href", ""))[:120]))
    return out


@check("SEC-HTM-002",
       title="iFrames ohne sandbox ## iframes without sandbox",
       why="Eingebettete Fremdinhalte laufen ohne sandbox mit vollen Rechten und können Nutzer täuschen oder "
           "Skripte ausführen. ## Embedded third-party content runs with full rights without sandbox and can "
           "deceive users or run scripts.",
       method="Sucht iframe ohne sandbox-Attribut; fremde Quellen werden strenger bewertet. ## "
              "Looks for iframe without sandbox attribute; third-party sources are rated more strictly.",
       logic="Fremde Quelle: Warnung, eigene Quelle: Info. ## Third-party source: warning, own source: info.",
       fix="sandbox=\"allow-scripts allow-same-origin\" nur mit den nötigen Rechten setzen. ## "
           "Set sandbox=\"allow-scripts allow-same-origin\" with only the required permissions.",
       refs=["https://html.spec.whatwg.org/multipage/iframe-embed-object.html#attr-iframe-sandbox", "https://owasp.org/www-community/attacks/Clickjacking"])
def iframes(snap):
    out = []
    for pg in snap.docs():
        for fr in pg.soup.find_all("iframe"):
            if fr.has_attr("sandbox"):
                continue
            src = urljoin(pg.url, str(fr.get("src", "")))
            ext = bool(urlsplit(src).hostname) and urlsplit(src).hostname != urlsplit(pg.url).hostname
            out.append(F("SEC-HTM-002", S.WARNING if ext else S.INFO, pg.url,
                         "iFrame ohne sandbox" + (" (fremde Quelle)" if ext else ""),
                         "iframe without sandbox" + (" (third-party source)" if ext else ""), src[:120]))
    return out


@check("SEC-SEC-001",
       title="Geheimnisse im Quelltext ## Secrets in source code",
       why="Versehentlich veröffentlichte API-Schlüssel, Tokens oder private Schlüssel erlauben Dritten den "
           "Zugriff auf Konten und Dienste. Das ist ein häufiger Fehler mit hohem Schaden. ## Accidentally "
           "published API keys, tokens or private keys give third parties access to accounts and services. "
           "A common mistake with high impact.",
       method="Mustersuche im HTML (inkl. Inline-Skripten) nach bekannten Schlüsselformaten. Im Bericht erscheinen "
              "Funde nur maskiert (Typ, erste 4 Zeichen, Länge). ## Pattern search in HTML (incl. inline scripts) "
              "for known key formats. The report shows findings only masked (type, first 4 characters, length).",
       logic="Privater Schlüssel: kritisch, sonst Fehler. ## Private key: critical, otherwise error.",
       fix="Schlüssel sofort widerrufen und erneuern, serverseitig speichern. ## "
           "Revoke and rotate the key immediately and keep it server-side.",
       refs=["https://owasp.org/Top10/A02_2021-Cryptographic_Failures/", "https://cwe.mitre.org/data/definitions/798.html"])
def secrets(snap):
    out = []
    for pg in snap.docs():
        for name, pat in SECRET_PATTERNS.items():
            for m in list(pat.finditer(pg.html))[:3]:
                sev = S.CRITICAL if name == "private_key" else S.ERROR
                out.append(F("SEC-SEC-001", sev, pg.url, f"Mögliches Geheimnis im Quelltext ({name})",
                             f"Possible secret in source code ({name})", mask_secret(m.group(0))))
    return out


@check("SEC-NET-001",
       title="Unsichere Verweise und Mixed Content ## Insecure links and mixed content",
       why="HTTP-Ressourcen auf HTTPS-Seiten werden blockiert oder können manipuliert werden; Weiterleitungen auf "
           "HTTP machen die Verschlüsselung wirkungslos. ## HTTP resources on HTTPS pages are blocked or can be "
           "tampered with; redirects to HTTP make encryption useless.",
       method="Prüft Weiterleitungen auf unverschlüsseltes HTTP sowie src/href von script, iframe, link, img, "
              "source, video, audio und a mit unverschlüsseltem HTTP. ## Checks redirects to unencrypted HTTP "
              "and src/href of script, iframe, link, img, source, video, audio and a using unencrypted HTTP.",
       logic="Skript/iFrame/CSS über HTTP oder HTTP-Weiterleitung: Fehler, Bilder/Medien: Warnung, Links: Hinweis. ## "
             "Script/iframe/CSS over HTTP or HTTP redirect: error, images/media: warning, links: note.",
       fix="Alle Ressourcen und Weiterleitungen auf HTTPS umstellen. ## Switch all resources and redirects to HTTPS.",
       refs=["https://www.w3.org/TR/mixed-content/", "https://owasp.org/www-project-web-security-testing-guide/"])
def mixed_content(snap):
    out = []
    for pg in snap.pages:
        if pg.downgrade:
            out.append(F("SEC-NET-001", S.ERROR, pg.url, "Weiterleitung auf unverschlüsseltes HTTP (nicht verfolgt)",
                         "Redirect to unencrypted HTTP (not followed)", pg.blocked_redirect or ""))
            continue
        if pg.html is None:
            continue
        for tag, attr, sev in (("script", "src", S.ERROR), ("iframe", "src", S.ERROR), ("link", "href", S.ERROR),
                               ("img", "src", S.WARNING), ("source", "src", S.WARNING),
                               ("video", "src", S.WARNING), ("audio", "src", S.WARNING)):
            for el in pg.soup.find_all(tag):
                v = str(el.get(attr, "")).strip()
                if v.lower().startswith("http:") and not (tag == "link" and "stylesheet" not in (el.get("rel") or [])):
                    out.append(F("SEC-NET-001", sev, pg.url, f"HTTP-Ressource ({tag}) auf HTTPS-Seite",
                                 f"HTTP resource ({tag}) on HTTPS page", v[:120]))
        if pg.insecure_links:
            out.append(F("SEC-NET-001", S.NOTE, pg.url, f"{len(pg.insecure_links)} Link(s) auf unverschlüsseltes HTTP",
                         f"{len(pg.insecure_links)} link(s) to unencrypted HTTP", pg.insecure_links[0][:120]))
    return out
