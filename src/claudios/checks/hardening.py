"""Härtungs-Prüfungen, die nur den Snapshot auswerten: CORS, Cache-Control, CSP-Reporting, E-Mail-Adressen, CMS."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from bs4 import Comment

from ..core.registry import check
from ._util import F, S
from .security import _csp

MDN = "https://developer.mozilla.org/en-US/docs/Web/HTTP/"
_LOGIN_PATH = re.compile(
    r"/(login|signin|sign-in|anmelden|konto|account|my-account|admin|wp-admin|checkout|kasse|warenkorb|cart)(/|$)",
    re.I)
# Lookbehind: ein Treffer beginnt nur am Anfang eines Zeichenlaufs (sonst quadratische Laufzeit bei langem Text).
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.([A-Za-z]{2,})")
_IMAGE_TLDS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "avif"}
_VERSION = re.compile(r"(\d+(?:\.\d+){1,3})")
_CMS_PATHS = (
    ("WordPress", re.compile(r"/wp-(?:content|includes)/")),
    ("Joomla", re.compile(r"/media/(?:system|jui)/|/components/com_")),
    ("Drupal", re.compile(r"/sites/(?:default|all)/(?:files|modules|themes)/|drupal-settings-json")),
    ("TYPO3", re.compile(r"typo3(?:conf|temp)/")),
    ("Shopify", re.compile(r"cdn\.shopify\.com|shopify\.theme")),
    ("Wix", re.compile(r"static\.wixstatic\.com")),
    ("Squarespace", re.compile(r"static1\.squarespace\.com")),
    ("Magento", re.compile(r"/skin/frontend/|/static/version\d+/")),
)
_CMS_NAMES = ("WordPress", "Joomla", "Drupal", "TYPO3", "Shopify", "Wix", "Squarespace", "Magento")


@check("SEC-COR-001",
       title="CORS-Freigabe ## CORS policy",
       why="CORS legt fest, welche fremden Seiten Antworten per Skript lesen dürfen. Zu offene Regeln ('*', 'null' "
           "oder eine Freigabe zusammen mit Cookies) erlauben fremden Seiten, Daten im Namen angemeldeter Nutzer "
           "abzufragen. ## CORS defines which foreign sites may read responses by script. Overly open rules "
           "('*', 'null' or a grant together with cookies) allow foreign sites to query data on behalf of "
           "signed-in users.",
       method="Liest Access-Control-Allow-Origin und Access-Control-Allow-Credentials aus den Antworten der "
              "gecrawlten HTML-Seiten (je Wertekombination ein Befund). Ob der Server beliebige Ursprünge "
              "spiegelt, wird nicht getestet, dafür wäre ein Origin-Header in der Anfrage nötig. Skripte und "
              "Bilder werden nicht abgerufen. ## Reads Access-Control-Allow-Origin and "
              "Access-Control-Allow-Credentials from the responses of the crawled HTML pages (one finding per "
              "combination of values). Whether the server reflects arbitrary origins is not tested, that would "
              "need an Origin header in the request. Scripts and images are not fetched.",
       logic="'*' zusammen mit Credentials: Fehler. 'null': Warnung. '*' allein: Hinweis (bei öffentlichen "
             "Inhalten oft gewollt). ## '*' together with credentials: error. 'null': warning. '*' alone: note "
             "(often intended for public content).",
       fix="Nur vertrauenswürdige Ursprünge einzeln freigeben, nie 'null' und nie Credentials zusammen mit '*'. ## "
           "Allow only trusted origins individually, never 'null' and never credentials together with '*'.",
       refs=["https://fetch.spec.whatwg.org/#http-cors-protocol", MDN + "CORS"])
def cors(snap):
    out, seen = [], set()
    for pg in snap.docs():
        origin = pg.headers.get("access-control-allow-origin", "").strip()
        creds = pg.headers.get("access-control-allow-credentials", "").strip().lower() == "true"
        if not origin or (origin, creds) in seen:
            continue
        if origin == "*" and creds:
            sev, de, en = S.ERROR, "CORS erlaubt alle Ursprünge zusammen mit Credentials", \
                "CORS allows all origins together with credentials"
        elif origin == "null":
            sev, de, en = S.WARNING, "CORS erlaubt den Ursprung 'null'", "CORS allows the origin 'null'"
        elif origin == "*":
            sev, de, en = S.NOTE, "CORS erlaubt alle Ursprünge (*)", "CORS allows all origins (*)"
        else:
            continue
        seen.add((origin, creds))
        out.append(F("SEC-COR-001", sev, pg.url, de, en, f"Access-Control-Allow-Origin: {origin}"))
    return out


@check("SEC-CCH-001",
       title="Cache-Control bei sensiblen Seiten ## Cache-Control on sensitive pages",
       why="Seiten mit Passwortfeld oder Anmeldebereich können sonst in Browser- und Proxy-Caches landen und "
           "später von anderen gesehen werden, etwa an gemeinsam genutzten Rechnern. ## Pages with a password "
           "field or sign-in area can otherwise end up in browser and proxy caches and be seen by others later, "
           "for example on shared computers.",
       method="Prüft Seiten mit Passwortfeld und Seiten, deren Pfad auf Anmeldung, Konto, Admin oder Kasse "
              "hindeutet, auf Cache-Control: no-store (oder private). ## Checks pages with a password field and "
              "pages whose path suggests sign-in, account, admin or checkout for Cache-Control: no-store (or "
              "private).",
       logic="Passwortfeld ohne no-store: Warnung. Anmeldepfad ohne no-store und private: Hinweis. ## Password "
             "field without no-store: warning. Sign-in path without no-store and private: note.",
       fix="Cache-Control: no-store für Anmelde-, Konto- und Kassenseiten senden. ## Send Cache-Control: no-store "
           "for sign-in, account and checkout pages.",
       refs=[MDN + "Headers/Cache-Control", "https://owasp.org/www-project-secure-headers/"])
def cache_control(snap):
    out = []
    for pg in snap.docs():
        cc = pg.headers.get("cache-control", "").lower()
        has_password = pg.soup.find("input", attrs={"type": re.compile("^password$", re.I)}) is not None
        if has_password and "no-store" not in cc:
            out.append(F("SEC-CCH-001", S.WARNING, pg.url, "Seite mit Passwortfeld ohne Cache-Control: no-store",
                         "Page with password field without Cache-Control: no-store", cc or "(kein Header)"))
        elif not has_password and _LOGIN_PATH.search(urlsplit(pg.url).path) \
                and "no-store" not in cc and "private" not in cc:
            out.append(F("SEC-CCH-001", S.NOTE, pg.url, "Anmelde- oder Kontoseite ohne Cache-Control: no-store",
                         "Sign-in or account page without Cache-Control: no-store", cc or "(kein Header)"))
    return out


@check("SEC-CSR-001",
       title="CSP-Berichte ## CSP reporting",
       why="Ohne Berichtsadresse bleiben Verstöße gegen die Content-Security-Policy unbemerkt, etwa eingeschleuste "
           "Skripte. Eine Richtlinie nur im Report-Only-Modus schützt gar nicht. ## Without a report endpoint "
           "violations of the Content-Security-Policy go unnoticed, for example injected scripts. A policy in "
           "report-only mode does not protect at all.",
       method="Sucht in der CSP die Direktiven report-uri oder report-to und prüft, ob nur "
              "Content-Security-Policy-Report-Only gesendet wird. ## Looks in the CSP for the directives "
              "report-uri or report-to and checks whether only Content-Security-Policy-Report-Only is sent.",
       logic="Nur Report-Only: Hinweis. Richtlinie ohne Berichtsadresse: Info. ## Report-only only: note. Policy "
             "without report endpoint: info.",
       fix="report-to (oder report-uri) ergänzen und die Richtlinie durchsetzen, sobald keine Verstöße mehr "
           "auftreten. ## Add report-to (or report-uri) and enforce the policy once no violations remain.",
       refs=["https://www.w3.org/TR/CSP3/#directive-report-to", MDN + "Headers/Content-Security-Policy-Report-Only"])
def csp_reporting(snap):
    out, flagged = [], set()
    for pg in snap.docs():
        enforced = pg.headers.get("content-security-policy", "")
        report_only = pg.headers.get("content-security-policy-report-only", "")
        if not enforced and report_only and "report_only" not in flagged:
            flagged.add("report_only")
            out.append(F("SEC-CSR-001", S.NOTE, pg.url, "CSP nur im Report-Only-Modus (schützt nicht)",
                         "CSP in report-only mode only (does not protect)"))
        elif enforced and "no_endpoint" not in flagged:
            directives = _csp(enforced)
            if "report-uri" not in directives and "report-to" not in directives:
                flagged.add("no_endpoint")
                out.append(F("SEC-CSR-001", S.INFO, pg.url, "CSP ohne Berichtsadresse (report-to/report-uri)",
                             "CSP without report endpoint (report-to/report-uri)"))
    return out


@check("SEC-EML-001",
       title="E-Mail-Adressen im Klartext ## E-mail addresses in plain text",
       why="Adressen im Klartext werden von Robotern gesammelt und für Spam und Phishing genutzt. Zugleich sind "
           "sie in manchen Ländern (zum Beispiel im Impressum in Deutschland) vorgeschrieben, deshalb ist das "
           "nur ein Hinweis. ## Addresses in plain text are harvested by bots and used for spam and phishing. "
           "In some countries (for example the legal notice in Germany) they are mandatory, so this is only an "
           "info.",
       method="Sucht im sichtbaren Text (ohne Skripte, Stile und Kommentare) und in mailto-Links aller gecrawlten "
              "Seiten nach Adressen und meldet einmal je Website die Anzahl. Die Adressen selbst erscheinen nie "
              "im Bericht. ## Searches the visible text (without scripts, styles and comments) and mailto links "
              "of all crawled pages for addresses and reports the count once per site. The addresses themselves "
              "never appear in the report.",
       logic="Mindestens eine Adresse: Info. ## At least one address: info.",
       fix="Wo möglich ein Kontaktformular oder eine Verschleierung per Skript verwenden. ## Where possible use a "
           "contact form or script-based obfuscation.",
       refs=["https://www.rfc-editor.org/rfc/rfc5322", "https://www.rfc-editor.org/rfc/rfc6068"],
       profiles="sd")
def email_addresses(snap):
    found, pages = set(), []
    for pg in snap.docs():
        soup = pg.soup
        mails = set()
        for string in soup.find_all(string=True):
            if isinstance(string, Comment) or string.parent.name in ("script", "style"):
                continue
            mails.update(m.group(0).lower() for m in _EMAIL.finditer(str(string))
                         if m.group(1).lower() not in _IMAGE_TLDS)
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if href.lower().startswith("mailto:"):
                mails.update(m.group(0).lower() for m in _EMAIL.finditer(href))
        if mails:
            found.update(mails)
            pages.append(pg.url)
    if not found:
        return []
    return [F("SEC-EML-001", S.INFO, pages[0],
              f"{len(found)} E-Mail-Adresse(n) im Klartext auf {len(pages)} Seite(n)",
              f"{len(found)} e-mail address(es) in plain text on {len(pages)} page(s)")]


@check("SEC-CMS-001",
       title="CMS-Erkennung und Versionsangaben ## CMS detection and version disclosure",
       why="Veraltete Versionen von Content-Management-Systemen sind das häufigste Einfallstor für Angriffe. Wer "
           "seine Version offen nennt, erleichtert gezielte Angriffe auf bekannte Schwachstellen. ## Outdated "
           "versions of content management systems are the most common entry point for attacks. Disclosing the "
           "exact version makes targeted attacks on known vulnerabilities easier.",
       method="Erkennt WordPress, Joomla, Drupal, TYPO3, Shopify, Wix, Squarespace und Magento an typischen "
              "Pfaden, dem Generator-Meta-Tag und dem Header X-Generator. Eine Schwachstellen-Datenbank gibt es "
              "noch nicht, deshalb wird nur gemeldet, was erkannt wurde und ob die Version sichtbar ist. ## "
              "Detects WordPress, Joomla, Drupal, TYPO3, Shopify, Wix, Squarespace and Magento from typical "
              "paths, the generator meta tag and the X-Generator header. There is no vulnerability database "
              "yet, so the check only reports what was detected and whether the version is visible.",
       logic="Version sichtbar: Hinweis. System erkannt, Version nicht sichtbar: Info. ## Version visible: note. "
             "System detected, version not visible: info.",
       fix="Das System aktuell halten und die Versionsangabe (Generator-Tag) entfernen. ## Keep the system "
           "up to date and remove the version disclosure (generator tag).",
       refs=["https://owasp.org/www-project-web-security-testing-guide/",
             "https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/"], profiles="sd")
def cms(snap):
    found: dict[str, dict] = {}

    def note(name: str, url: str, version: str | None, evidence: str) -> None:
        entry = found.setdefault(name, {"url": url, "version": None, "evidence": ""})
        if version and not entry["version"]:
            entry.update(version=version, evidence=evidence, url=url)

    for pg in snap.docs():
        html = pg.html.lower()
        for name, pattern in _CMS_PATHS:
            if pattern.search(html):
                note(name, pg.url, None, "")
        sources = [str(m.get("content", "")) for m in
                   pg.soup.find_all("meta", attrs={"name": re.compile("^generator$", re.I)})]
        sources.append(pg.headers.get("x-generator", ""))
        for text in sources:
            for name in _CMS_NAMES:
                if name.lower() in text.lower():
                    match = _VERSION.search(text)
                    note(name, pg.url, match.group(1) if match else None, text[:80])
    out = []
    for name, entry in sorted(found.items()):
        if entry["version"]:
            out.append(F("SEC-CMS-001", S.NOTE, entry["url"], f"{name} {entry['version']} verrät seine Version",
                         f"{name} {entry['version']} reveals its version", entry["evidence"]))
        else:
            out.append(F("SEC-CMS-001", S.INFO, entry["url"],
                         f"{name} erkannt (Version nicht sichtbar, bitte Updates prüfen)",
                         f"{name} detected (version not visible, please check for updates)"))
    return out
