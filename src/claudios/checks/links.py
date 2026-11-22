"""Link-Prüfungen. Interne Links, Anker, mailto/tel und Link-Texte werten nur den Snapshot aus,
externe Links stammen aus der Probe-Phase."""
from __future__ import annotations

import re
from urllib.parse import unquote

from ..core.crawler import norm
from ..core.redact import redact_url
from ..core.registry import check
from ._util import CheckSkipped, F, S

RFC = "https://www.rfc-editor.org/rfc/"
GOOGLE_LINKS = "https://developers.google.com/search/docs/crawling-indexing/links-crawlable"
WCAG_LINK = "https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html"
_MAIL = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}")
_TEL = re.compile(r"\+?[0-9][0-9 ()./-]{3,}")
_GENERIC = {"hier", "hier klicken", "klick hier", "klicken sie hier", "mehr", "mehr lesen", "mehr erfahren",
            "weiterlesen", "link", "click here", "here", "more", "read more", "learn more"}


@check("LNK-INT-001",
       title="Kaputte interne Links ## Broken internal links",
       why="Interne Links auf Fehlerseiten verschlechtern die Nutzererfahrung und verschwenden das Crawl-Budget "
           "von Suchmaschinen. ## Internal links to error pages worsen the user experience and waste the crawl "
           "budget of search engines.",
       method="Wertet die Antworten aller gecrawlten Seiten aus und nennt die verlinkende Seite. Seiten außerhalb "
              "von Ebenen- und Seitenlimit werden nicht abgerufen. ## Evaluates the responses of all crawled pages "
              "and names the linking page. Pages beyond the level and page limit are not fetched.",
       logic="HTTP 404 oder 410: Fehler. Andere Fehlercodes oder nicht erreichbar: Warnung. ## "
             "HTTP 404 or 410: error. Other error codes or unreachable: warning.",
       fix="Link korrigieren oder entfernen, bei verschobenen Inhalten eine 301-Weiterleitung einrichten. ## "
           "Fix or remove the link, and set up a 301 redirect for moved content.",
       refs=[GOOGLE_LINKS, RFC + "rfc9110.html#name-client-error-4xx"], profiles="sd")
def internal_links(snap):
    out = []
    link_sets = {id(p): {norm(x) for x in p.internal_links} for p in snap.pages}
    for pg in snap.pages:
        failed = pg.error is not None
        if not failed and not (pg.status is not None and pg.status >= 400):
            continue
        first = norm(pg.chain[0] if pg.chain else pg.url)
        sources = [p.url for p in snap.pages if p is not pg and first in link_sets[id(p)]][:3]
        evidence = f"← {sources[0]}" if sources else ""
        if failed:
            out.append(F("LNK-INT-001", S.WARNING, pg.url, "Interne Seite nicht erreichbar",
                         "Internal page unreachable", evidence))
        elif pg.status in (404, 410):
            out.append(F("LNK-INT-001", S.ERROR, pg.url, f"Interner Link führt zu HTTP {pg.status}",
                         f"Internal link leads to HTTP {pg.status}", evidence))
        else:
            out.append(F("LNK-INT-001", S.WARNING, pg.url, f"Interne Seite antwortet mit HTTP {pg.status}",
                         f"Internal page answers with HTTP {pg.status}", evidence))
    return out


@check("LNK-RED-001",
       title="Weiterleitungsketten ## Redirect chains",
       why="Jede Weiterleitung kostet Ladezeit, und lange Ketten verlieren Ranking-Signale. ## "
           "Every redirect costs loading time and long chains lose ranking signals.",
       method="Zählt die Weiterleitungen, die beim Abruf jeder gecrawlten Seite auftraten. ## "
              "Counts the redirects that occurred when fetching each crawled page.",
       logic="Zwei oder mehr Weiterleitungen hintereinander: Hinweis. ## Two or more redirects in a row: note.",
       fix="Links und Weiterleitungen direkt auf die endgültige Adresse zeigen lassen. ## "
           "Point links and redirects directly to the final address.",
       refs=[GOOGLE_LINKS, RFC + "rfc9110.html#name-redirection-3xx"], profiles="sd")
def redirect_chains(snap):
    return [F("LNK-RED-001", S.NOTE, pg.url, f"Weiterleitungskette mit {len(pg.chain)} Schritten",
              f"Redirect chain with {len(pg.chain)} steps", f"{redact_url(pg.chain[0])} → {redact_url(pg.url)}")
            for pg in snap.pages if len(pg.chain) >= 2]


@check("LNK-EXT-001",
       title="Kaputte externe Links ## Broken external links",
       why="Defekte externe Links zeigen veraltete Inhalte und wirken unseriös. ## "
           "Broken external links show outdated content and look unprofessional.",
       method="Jede eindeutige externe https-Adresse wird höchstens einmal mit HEAD (bei Ablehnung mit GET) über den "
              "gedrosselten Gatekeeper geprüft: höchstens 200 Adressen und 5 Minuten, "
               "je Adresse 8 Sekunden. Weiterleitungen werden nicht verfolgt (nur der erste Statuscode zählt), "
               "träge Server werden nach zwei Zeitüberschreitungen übersprungen."
               " Externe Seiten werden nicht "
              "gecrawlt, Links auf unverschlüsseltes HTTP werden nicht abgerufen. ## Every unique external https "
              "address is checked at most once with HEAD (GET if rejected) through the throttled gatekeeper: at "
              "most 200 addresses and 5 minutes, "
               "8 seconds per address. Redirects are not followed (only the first status code counts), "
               "and slow servers are skipped after two timeouts."
               " External sites are not crawled, links to unencrypted HTTP are "
              "not fetched.",
       logic="HTTP 404/410 oder ungültiges Zertifikat: Fehler. Andere 4xx/5xx oder nicht erreichbar: Warnung. "
             "401/403/429/999: Info (Server verweigert Prüfung). Nicht geprüfte Reste: Info. ## "
             "HTTP 404/410 or invalid certificate: error. Other 4xx/5xx or unreachable: warning. 401/403/429/999: "
             "info (server refuses the check). Unchecked remainder: info.",
       fix="Link ersetzen oder entfernen. ## Replace or remove the link.",
       refs=[GOOGLE_LINKS, RFC + "rfc9110.html#name-status-codes"], profiles="sd", source="network")
def external_links(snap):
    data = snap.extra.get("links")
    if data is None:
        raise CheckSkipped("no_link_data")
    out = []
    for rec in data["results"]:
        status, err = rec["status"], rec["error"]
        src, target = rec["sources"][0], redact_url(rec["url"])
        if err:
            if err == "CLA-TLS-001":
                sev, de, en = S.ERROR, "Externer Link: Zertifikat ungültig", "External link: invalid certificate"
            elif err in ("CLA-NET-001", "CLA-NET-002", "CLA-NET-003", "CLA-TGT-002", "CLA-TLS-002"):
                sev, de, en = S.WARNING, "Externer Link nicht erreichbar", "External link unreachable"
            else:
                sev, de, en = (S.NOTE, "Externer Link konnte nicht geprüft werden", "External link could not be checked")
        elif status is not None and status >= 400:
            if status in (404, 410):
                sev, de, en = (S.ERROR, f"Externer Link defekt (HTTP {status})", f"Broken external link (HTTP {status})")
            elif status in (401, 403, 429, 999):
                sev, de, en = (S.INFO, f"Externer Server verweigert die Prüfung (HTTP {status})",
                               f"External server refuses the check (HTTP {status})")
            else:
                sev, de, en = (S.WARNING, f"Externer Link liefert HTTP {status}", f"External link returns HTTP {status}")
        else:
            continue
        out.append(F("LNK-EXT-001", sev, src, de, en, target))
    rest = data["unique"] - data["checked"]
    if rest > 0:
        out.append(F("LNK-EXT-001", S.INFO, snap.target.url, f"{rest} externe Links nicht geprüft (Limit oder Zeitbudget)",
                     f"{rest} external links not checked (limit or time budget)"))
    return out


@check("LNK-ANC-001",
       title="Sprungmarken ohne Ziel ## Anchor links without target",
       why="Ein Link auf #abschnitt, dessen Ziel nicht existiert, springt ins Leere. ## "
           "A link to #section whose target does not exist jumps nowhere.",
       method="Vergleicht href=\"#...\" mit den id- und name-Attributen derselben Seite. ## "
              "Compares href=\"#...\" with the id and name attributes of the same page.",
       logic="Hinweis je Seite mit fehlenden Zielen. ## Note per page with missing targets.",
       fix="Passende id vergeben oder den Link korrigieren. ## Add a matching id or fix the link.",
       refs=["https://html.spec.whatwg.org/multipage/browsing-the-web.html#scroll-to-fragid"], profiles="sd")
def anchors(snap):
    out = []
    for pg in snap.docs():
        soup = pg.soup
        ids = {str(e["id"]) for e in soup.find_all(id=True)}
        ids |= {str(a["name"]) for a in soup.find_all("a", attrs={"name": True})}
        missing = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if len(href) < 2 or not href.startswith("#"):
                continue
            target = unquote(href[1:])
            if target.lower() == "top" or target.startswith(("!", "/")):
                continue
            if target not in ids:
                missing.append(target)
        if missing:
            out.append(F("LNK-ANC-001", S.NOTE, pg.url, f"{len(missing)} Sprungmarke(n) ohne Ziel",
                         f"{len(missing)} anchor link(s) without target", "#" + missing[0]))
    return out


@check("LNK-MAI-001",
       title="mailto- und tel-Links ## mailto and tel links",
       why="Ein fehlerhafter Kontaktlink lässt Besucher ohne Möglichkeit, Sie zu erreichen. ## "
           "A faulty contact link leaves visitors without a way to reach you.",
       method="Prüft die Syntax von mailto:-Adressen und tel:-Nummern. ## "
              "Checks the syntax of mailto: addresses and tel: numbers.",
       logic="Ungültige E-Mail-Adresse: Warnung. Ungültige Telefonnummer: Hinweis. ## "
             "Invalid e-mail address: warning. Invalid phone number: note.",
       fix="Form mailto:name@domain.example bzw. tel:+4930123456 verwenden. ## "
           "Use the form mailto:name@domain.example or tel:+4930123456.",
       refs=[RFC + "rfc6068", RFC + "rfc3966"], profiles="sd")
def mail_tel(snap):
    out = []
    for pg in snap.docs():
        bad_mail, bad_tel = [], []
        for a in pg.soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            low = href.lower()
            if low.startswith("mailto:"):
                parts = [x.strip() for x in unquote(href[7:].split("?", 1)[0]).split(",") if x.strip()]
                if not parts or not all(_MAIL.fullmatch(x) for x in parts):
                    bad_mail.append(href)
            elif low.startswith("tel:"):
                number = unquote(href[4:]).split(";", 1)[0].strip()
                if not _TEL.fullmatch(number):
                    bad_tel.append(href)
        if bad_mail:
            out.append(F("LNK-MAI-001", S.WARNING, pg.url, f"{len(bad_mail)} ungültige(r) mailto-Link(s)",
                         f"{len(bad_mail)} invalid mailto link(s)", bad_mail[0][:80]))
        if bad_tel:
            out.append(F("LNK-MAI-001", S.NOTE, pg.url, f"{len(bad_tel)} ungültige(r) tel-Link(s)",
                         f"{len(bad_tel)} invalid tel link(s)", bad_tel[0][:80]))
    return out


@check("LNK-TXT-001",
       title="Aussagekräftige Link-Texte ## Meaningful link text",
       why="Links wie 'hier klicken' oder ohne Text sind für Screenreader-Nutzer unbrauchbar (WCAG 2.4.4) und "
           "geben Suchmaschinen keinen Kontext. ## Links such as 'click here' or without text are useless for "
           "screen-reader users (WCAG 2.4.4) and give search engines no context.",
       method="Prüft den sichtbaren Text jedes Links, ersatzweise aria-label, title, Bild-alt oder ein SVG mit title. ## "
              "Checks the visible text of every link, alternatively aria-label, title, image alt or an SVG with title.",
       logic="Link ohne zugänglichen Namen: Warnung. Allgemeiner Text wie 'hier' oder 'mehr': Hinweis. ## "
             "Link without an accessible name: warning. Generic text such as 'here' or 'more': note.",
       fix="Beschreibenden Linktext verwenden, z. B. 'Preisliste 2025 ansehen' statt 'hier'. ## "
           "Use descriptive link text, e.g. 'View the 2025 price list' instead of 'here'.",
       refs=[WCAG_LINK, GOOGLE_LINKS], profiles="sd")
def link_text(snap):
    out = []
    for pg in snap.docs():
        empty, generic = [], []
        for a in pg.soup.find_all("a", href=True):
            text = " ".join(a.get_text(" ", strip=True).split()).lower().strip(" .…»>")
            if text:
                if text in _GENERIC:
                    generic.append(str(a["href"])[:80])
                continue
            image_alt = any(str(i.get("alt", "")).strip() for i in a.find_all("img"))
            svg_named = a.find("svg") is not None and a.find("title") is not None
            labelled = any(str(a.get(attr, "")).strip() for attr in ("aria-label", "title", "aria-labelledby"))
            if not (image_alt or svg_named or labelled):
                empty.append(str(a["href"])[:80])
        if empty:
            out.append(F("LNK-TXT-001", S.WARNING, pg.url, f"{len(empty)} Link(s) ohne zugänglichen Text",
                         f"{len(empty)} link(s) without accessible text", empty[0]))
        if generic:
            out.append(F("LNK-TXT-001", S.NOTE, pg.url, f"{len(generic)} Link(s) mit allgemeinem Text",
                         f"{len(generic)} link(s) with generic text", generic[0]))
    return out
