"""Weitere HTML- und Barrierefreiheits-Prüfungen, die nur den Snapshot auswerten: doppelte IDs, Überschriften,
Landmarks und Formulare."""
from __future__ import annotations

import re
from collections import Counter

from ..core.registry import check
from ._util import F, S

W3C = "https://html.spec.whatwg.org/multipage/"
WCAG = "https://www.w3.org/WAI/WCAG22/Understanding/"
_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
_NO_NAME_TYPES = {"hidden", "submit", "button", "image", "reset"}


@check("HTM-IDS-001",
       title="Doppelte IDs ## Duplicate IDs",
       why="Eine ID darf pro Dokument nur einmal vorkommen. Doppelte IDs brechen Sprungmarken, Beschriftungen "
           "(label for) und ARIA-Verweise und lassen Skripte das falsche Element treffen. ## An ID may occur only "
           "once per document. Duplicate IDs break anchors, labels (label for) and ARIA references and make scripts "
           "hit the wrong element.",
       method="Zählt je Seite alle id-Attribute (ohne Skripte) und meldet doppelte, leere und solche mit "
              "Leerzeichen. ## Counts all id attributes per page and reports duplicate, empty and spaced ones.",
       logic="Doppelte ID: Warnung. Leere ID oder ID mit Leerzeichen: Hinweis. ## Duplicate ID: warning. Empty ID "
             "or ID with spaces: note.",
       fix="Jede ID im Dokument eindeutig machen, ohne Leerzeichen. ## Make every ID in the document unique, without "
           "spaces.",
       refs=[W3C + "dom.html#the-id-attribute", WCAG + "parsing.html"])
def duplicate_ids(snap):
    out = []
    for pg in snap.docs():
        counts = Counter(str(el.get("id")).strip() for el in pg.soup.find_all(id=True))
        dups = sorted(k for k, c in counts.items() if k and c > 1)
        if dups:
            out.append(F("HTM-IDS-001", S.WARNING, pg.url, f"{len(dups)} doppelte ID(s) im Dokument",
                         f"{len(dups)} duplicate ID(s) in the document", ", ".join(dups[:3])))
        if counts.get(""):
            out.append(F("HTM-IDS-001", S.NOTE, pg.url, "Leeres id-Attribut", "Empty id attribute"))
        if any(" " in key for key in counts):
            out.append(F("HTM-IDS-001", S.NOTE, pg.url, "ID mit Leerzeichen", "ID containing spaces"))
    return out


def _heading_text(head) -> str:
    text = head.get_text(strip=True)
    if text:
        return text
    label = str(head.get("aria-label") or "").strip()
    if label:
        return label
    for img in head.find_all("img", limit=3):
        alt = str(img.get("alt") or "").strip()
        if alt:
            return alt
    return ""


@check("HTM-HDG-001",
       title="Überschriftenstruktur ## Heading structure",
       why="Überschriften gliedern eine Seite für Screenreader-Nutzer, die damit springen, und für Suchmaschinen. "
           "Fehlende, leere oder übersprungene Ebenen erschweren beides. ## Headings structure a page for "
           "screen-reader users, who jump with them, and for search engines. Missing, empty or skipped levels "
           "make both harder.",
       method="Liest h1 bis h6 je Seite: ob eine h1 vorhanden ist, ob Überschriften leer sind (auch ohne "
              "aria-label oder Bild-Alt) und ob eine Ebene übersprungen wird. ## Reads h1 to h6 per page: whether an "
              "h1 exists, whether headings are empty (also without aria-label or image alt) and whether a level is "
              "skipped.",
       logic="Leere Überschrift: Warnung. Keine h1 oder übersprungene Ebene: Hinweis. Mehrere h1: Info. ## Empty "
             "heading: warning. No h1 or skipped level: note. Several h1: info.",
       fix="Genau eine h1 je Seite, danach Ebenen lückenlos nutzen und keine leeren Überschriften ausgeben. ## Use "
           "exactly one h1 per page, then levels without gaps, and output no empty headings.",
       refs=[WCAG + "info-and-relationships.html", W3C + "sections.html#headings-and-outlines"])
def headings(snap):
    out = []
    for pg in snap.docs():
        heads = pg.soup.find_all(_HEADINGS, limit=300)
        ones = sum(1 for h in heads if h.name == "h1")
        if ones == 0:
            out.append(F("HTM-HDG-001", S.NOTE, pg.url, "Keine h1-Überschrift", "No h1 heading"))
        elif ones > 1:
            out.append(F("HTM-HDG-001", S.INFO, pg.url, f"{ones} h1-Überschriften auf einer Seite",
                         f"{ones} h1 headings on one page"))
        empty = [h for h in heads if not _heading_text(h)]
        if empty:
            out.append(F("HTM-HDG-001", S.WARNING, pg.url, f"{len(empty)} leere Überschrift(en)",
                         f"{len(empty)} empty heading(s)"))
        levels = [int(h.name[1]) for h in heads]
        jump = next(((a, b) for a, b in zip(levels, levels[1:], strict=False) if b > a + 1), None)
        if jump:
            out.append(F("HTM-HDG-001", S.NOTE, pg.url, f"Überschriftenebene übersprungen (h{jump[0]} → h{jump[1]})",
                         f"Heading level skipped (h{jump[0]} → h{jump[1]})"))
    return out


@check("HTM-LND-001",
       title="Landmarks (main, nav) ## Landmarks (main, nav)",
       why="Landmarks wie main und nav erlauben Screenreader-Nutzern, direkt zum Hauptinhalt oder zur Navigation zu "
           "springen. Mehrere main-Elemente sind ungültig und verwirren die Hilfsmittel. ## Landmarks such as main "
           "and nav let screen-reader users jump straight to the main content or the navigation. Several main "
           "elements are invalid and confuse assistive technology.",
       method="Sucht je Seite main (oder role=main) und nav-Elemente und prüft, ob mehrere nav einen Namen haben. "
              "## Looks per page for main (or role=main) and nav elements and checks whether several nav elements "
              "have a name.",
       logic="Mehrere sichtbare main: Warnung. Kein main: Hinweis. Mehrere nav ohne aria-label: Info. ## Several "
             "visible main: warning. No main: note. Several nav without aria-label: info.",
       fix="Genau ein main-Element mit dem Hauptinhalt, mehrere nav mit aria-label unterscheiden. ## Exactly one "
           "main element with the main content; tell several nav elements apart with aria-label.",
       refs=[WCAG + "info-and-relationships.html", "https://www.w3.org/WAI/ARIA/apg/practices/landmark-regions/"])
def landmarks(snap):
    out = []
    for pg in snap.docs():
        soup = pg.soup
        mains = {id(m): m for m in soup.find_all("main") if not m.has_attr("hidden")}
        mains.update({id(m): m for m in soup.find_all(attrs={"role": "main"})})
        if not mains:
            out.append(F("HTM-LND-001", S.NOTE, pg.url, "Kein main-Element", "No main element"))
        elif len(mains) > 1:
            out.append(F("HTM-LND-001", S.WARNING, pg.url, f"{len(mains)} main-Elemente (nur eines ist erlaubt)",
                         f"{len(mains)} main elements (only one is allowed)"))
        navs = soup.find_all("nav", limit=50)
        unnamed = [n for n in navs if not (n.get("aria-label") or n.get("aria-labelledby") or n.get("title"))]
        if len(navs) > 1 and unnamed:
            out.append(F("HTM-LND-001", S.INFO, pg.url, f"{len(navs)} nav-Elemente, {len(unnamed)} ohne Namen",
                         f"{len(navs)} nav elements, {len(unnamed)} without a name"))
    return out


def _has_name(field, label_ids: set[str]) -> bool:
    for attr in ("aria-label", "aria-labelledby", "title"):
        if str(field.get(attr) or "").strip():
            return True
    if str(field.get("id") or "") in label_ids:
        return True
    return field.find_parent("label") is not None


@check("HTM-FRM-001",
       title="Formulare (Beschriftung, Übertragung) ## Forms (labels, transmission)",
       why="Formularfelder ohne Beschriftung sind für Screenreader-Nutzer nicht bedienbar (WCAG 1.3.1, 4.1.2). Ein "
           "Formular, das über unverschlüsseltes HTTP sendet, oder ein Passwort per GET gibt Daten preis. ## Form "
           "fields without a label cannot be used by screen-reader users (WCAG 1.3.1, 4.1.2). A form that submits "
           "over unencrypted HTTP, or a password sent by GET, exposes data.",
       method="Prüft je Seite bis zu 500 Felder auf einen zugänglichen Namen (label for, umschließendes label, "
              "aria-label, aria-labelledby, title; Placeholder zählt nicht) sowie bis zu 50 Formulare auf "
              "http-Ziel und GET mit Passwortfeld. ## Checks per page up to 500 fields for an accessible name "
              "(label for, wrapping label, aria-label, aria-labelledby, title; a placeholder does not count) and up "
              "to 50 forms for an http target and GET with a password field.",
       logic="Formular sendet über HTTP: Fehler. Feld ohne Namen oder Passwort per GET: Warnung. ## Form submits "
             "over HTTP: error. Field without a name or password by GET: warning.",
       fix="Jedes Feld mit label for oder aria-label versehen, Formulare nur an https-Adressen senden lassen und "
           "Passwörter nur per POST übertragen. ## Give every field a label for or aria-label, let forms submit only "
           "to https addresses and send passwords only by POST.",
       refs=[WCAG + "labels-or-instructions.html", W3C + "forms.html"])
def forms(snap):
    out = []
    for pg in snap.docs():
        soup = pg.soup
        label_ids = {str(lab.get("for")) for lab in soup.find_all("label", attrs={"for": True}, limit=1000)}
        unnamed = []
        for field in soup.find_all(["input", "select", "textarea"], limit=500):
            if field.name == "input" and str(field.get("type") or "text").lower() in _NO_NAME_TYPES:
                continue
            if not _has_name(field, label_ids):
                unnamed.append(field)
        if unnamed:
            first = unnamed[0]
            hint = str(first.get("name") or first.get("placeholder") or first.get("type") or "")[:60]
            out.append(F("HTM-FRM-001", S.WARNING, pg.url, f"{len(unnamed)} Formularfeld(er) ohne Beschriftung",
                         f"{len(unnamed)} form field(s) without a label", hint))
        for form in soup.find_all("form", limit=50):
            action = str(form.get("action") or "").strip().lower()
            if action.startswith("http:"):
                out.append(F("HTM-FRM-001", S.ERROR, pg.url, "Formular sendet über unverschlüsseltes HTTP",
                             "Form submits over unencrypted HTTP", action[:80]))
            method = str(form.get("method") or "get").strip().lower()
            if method == "get" and form.find("input", attrs={"type": re.compile("^password$", re.I)}) is not None:
                out.append(F("HTM-FRM-001", S.WARNING, pg.url, "Formular mit Passwortfeld sendet per GET (Passwort in der URL)",
                             "Form with password field submits by GET (password in the URL)"))
    return out
