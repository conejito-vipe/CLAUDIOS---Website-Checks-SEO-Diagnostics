from __future__ import annotations

import re

from ..core.registry import check
from ._util import F, S

W3C = "https://html.spec.whatwg.org/multipage/"


@check("HTM-STR-001",
       title="Grundstruktur des Dokuments ## Document structure",
       why="Fehlender Doctype löst den Quirks-Modus aus, fehlendes lang/charset führt zu falscher Darstellung, "
           "Silbentrennung und Vorlesen, ein fehlender Titel schadet Nutzern und Suchmaschinen. ## "
           "A missing doctype triggers quirks mode, missing lang/charset causes wrong rendering, hyphenation and "
           "screen-reader pronunciation, and a missing title hurts users and search engines.",
       method="Auswertung des HTML je Seite: Doctype, html[lang], meta charset oder Content-Type-Charset, title, "
              "meta viewport. ## Per-page HTML evaluation: doctype, html[lang], meta charset or Content-Type "
              "charset, title, meta viewport.",
       logic="Doctype/lang/charset fehlen: Warnung. Titel fehlt: Fehler. Viewport fehlt: Hinweis. ## "
             "Missing doctype/lang/charset: warning. Missing title: error. Missing viewport: note.",
       fix="<!doctype html>, <html lang=\"de\">, <meta charset=\"utf-8\">, <title> und viewport-Meta ergänzen. ## "
           "Add <!doctype html>, <html lang=\"en\">, <meta charset=\"utf-8\">, <title> and viewport meta.",
       refs=[W3C + "semantics.html#the-html-element", "https://validator.w3.org/nu/"])
def structure(snap):
    out = []
    for pg in snap.docs():
        soup = pg.soup
        if not re.match(r"\s*<!doctype html", pg.html[:300], re.I):
            out.append(F("HTM-STR-001", S.WARNING, pg.url, "Doctype fehlt", "Doctype missing"))
        html = soup.find("html")
        if not html or not str(html.get("lang", "")).strip():
            out.append(F("HTM-STR-001", S.WARNING, pg.url, "Attribut lang am html-Element fehlt", "html lang attribute missing"))
        has_cs = (soup.find("meta", attrs={"charset": True}) or "charset=" in pg.content_type
                  or soup.find("meta", attrs={"http-equiv": re.compile("content-type", re.I)}))
        if not has_cs:
            out.append(F("HTM-STR-001", S.WARNING, pg.url, "Zeichensatz (charset) nicht deklariert", "Character set (charset) not declared"))
        if not (soup.title and soup.title.get_text(strip=True)):
            out.append(F("HTM-STR-001", S.ERROR, pg.url, "Seitentitel fehlt oder ist leer", "Page title missing or empty"))
        if not soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}):
            out.append(F("HTM-STR-001", S.NOTE, pg.url, "Viewport-Meta fehlt (mobile Darstellung)", "Viewport meta missing (mobile rendering)"))
    return out


@check("HTM-IMG-001",
       title="Bilder ohne Alternativtext ## Images without alternative text",
       why="Ohne alt-Attribut können Screenreader-Nutzer Bilder nicht erfassen (WCAG 1.1.1), und Suchmaschinen "
           "verstehen den Bildinhalt nicht. ## Without an alt attribute screen-reader users cannot perceive "
           "images (WCAG 1.1.1) and search engines cannot understand the image content.",
       method="Zählt img-Elemente ohne alt-Attribut je Seite (alt=\"\" für dekorative Bilder ist erlaubt). ## "
              "Counts img elements without alt attribute per page (alt=\"\" for decorative images is allowed).",
       logic="Warnung, sobald mindestens ein Bild betroffen ist. ## Warning as soon as at least one image is affected.",
       fix="alt=\"Beschreibung\" ergänzen oder alt=\"\" für rein dekorative Bilder. ## "
           "Add alt=\"description\" or alt=\"\" for purely decorative images.",
       refs=[W3C + "embedded-content.html#attr-img-alt", "https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html"])
def images_alt(snap):
    out = []
    for pg in snap.docs():
        bad = [i for i in pg.soup.find_all("img") if i.get("alt") is None]
        if bad:
            out.append(F("HTM-IMG-001", S.WARNING, pg.url, f"{len(bad)} Bild(er) ohne alt-Attribut",
                         f"{len(bad)} image(s) without alt attribute", str(bad[0].get("src", ""))[:120]))
    return out
