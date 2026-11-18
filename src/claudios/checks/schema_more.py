"""Weitere SEO-Prüfungen auf Basis von Schema.org und Seitenstruktur: Tiefe der strukturierten Daten, Vertrauenssignale
(E-E-A-T-Indizien), Struktur für KI-Antworten (GEO), lokales SEO und Shop-Daten. Alles sind Indizien aus dem HTML,
keine Bewertung durch Google. Höchstens Hinweise."""
from __future__ import annotations

import re

from ..core.registry import check
from . import _schema
from ._util import F, S
from .seo_extra import _words

GOOGLE = "https://developers.google.com/search/docs/"
SCHEMA = "https://schema.org/"
REQUIRED = {
    "organization": ("name", "url"), "website": ("name", "url"), "person": ("name",),
    "product": ("name", "image", "offers"), "article": ("headline", "datePublished", "author", "image"),
    "faqpage": ("mainEntity",), "breadcrumblist": ("itemListElement",), "event": ("name", "startDate", "location"),
    "videoobject": ("name", "thumbnailUrl", "uploadDate"), "jobposting": ("title", "datePosted", "hiringOrganization", "description"),
    "recipe": ("name", "image"), "review": ("itemReviewed", "reviewRating", "author"),
}


def _kinds(types: set[str]) -> list[str]:
    out = {"article" for t in types if t in _schema.ARTICLE_TYPES}
    out.update(t for t in types if t in REQUIRED)
    return sorted(out)


@check("SEO-SCH-001",
       title="Schema.org: Tiefe der strukturierten Daten ## Schema.org: depth of structured data",
       why="Strukturierte Daten helfen Suchmaschinen nur, wenn die wichtigsten Felder des Typs ausgefüllt sind. Ein Product ohne "
           "Preis oder ein Article ohne Autor wird für Rich Results oft ignoriert. ## Structured data only helps search engines "
           "if the most important fields of the type are filled in. A Product without a price or an Article without an author is "
           "often ignored for rich results.",
       method="Liest alle JSON-LD-Objekte (auch aus @graph) und prüft für 12 häufige Typen (Organization, WebSite, Person, "
              "Product, Article, FAQPage, BreadcrumbList, Event, VideoObject, JobPosting, Recipe, Review) eine kurze Liste "
              "wichtiger Felder; bei Product zusätzlich Preis, Währung und Verfügbarkeit im Angebot. Die Listen sind eine "
              "vereinfachte Auswahl, nicht die vollständigen Google-Anforderungen. Ob Daten fehlen, meldet SEO-STR-001. ## Reads "
              "all JSON-LD objects (also from @graph) and checks a short list of important fields for 12 common types "
              "(Organization, WebSite, Person, Product, Article, FAQPage, BreadcrumbList, Event, VideoObject, JobPosting, Recipe, "
              "Review); for Product also price, currency and availability in the offer. The lists are a simplified selection, not "
              "the full Google requirements. Whether data is missing at all is reported by SEO-STR-001.",
       logic="Wichtige Felder fehlen: Hinweis, je Typ und Fehlmenge ein Befund. ## Important fields missing: note, one finding "
             "per type and set of missing fields.",
       fix="Die fehlenden Felder ergänzen und im Rich-Results-Test von Google prüfen. ## Add the missing fields and verify them in "
           "Google's Rich Results Test.",
       refs=[GOOGLE + "appearance/structured-data/search-gallery", SCHEMA + "docs/gs.html"], profiles="sd")
def schema_depth(snap):
    seen: dict[tuple, set[str]] = {}
    for pg in snap.docs():
        for item in _schema.items(pg):
            kinds = _schema.types_of(item)
            for kind in _kinds(kinds):
                missing = tuple(p for p in REQUIRED[kind] if not _schema.has(item, p))
                if missing:
                    seen.setdefault((kind, missing), set()).add(pg.url)
            if "product" in kinds and _schema.has(item, "offers"):
                offer = _schema.first_dict(item.get("offers"))
                gaps = []
                if not any(_schema.has(offer, p) for p in ("price", "lowPrice", "priceSpecification")):
                    gaps.append("price")
                for prop in ("priceCurrency", "availability"):
                    if not _schema.has(offer, prop):
                        gaps.append(prop)
                if gaps:
                    seen.setdefault(("product.offers", tuple(gaps)), set()).add(pg.url)
    out = []
    for (kind, missing), urls in sorted(seen.items()):
        first = sorted(urls)[0]
        out.append(F("SEO-SCH-001", S.NOTE, first,
                     f"Schema.org {kind}: es fehlen {', '.join(missing)} ({len(urls)} Seite(n))",
                     f"Schema.org {kind}: missing {', '.join(missing)} ({len(urls)} page(s))"))
    return out


_ABOUT = re.compile(r"(about|über|ueber|uber-uns|team|unternehmen|company|who-we)", re.I)
_CONTACT = re.compile(r"(contact|kontakt)", re.I)
_LEGAL = re.compile(r"(impressum|imprint|legal-notice|anbieterkennzeichnung)", re.I)
_AUTHOR_CLASS = re.compile(r"(author|byline|autor)", re.I)


def _anchor_texts(pg):
    for a in pg.soup.find_all("a", href=True, limit=500):
        yield (str(a["href"]) + " " + a.get_text(" ", strip=True)).lower()


def _has_author(pg, items) -> bool:
    soup = pg.soup
    return bool(soup.find(attrs={"rel": "author"}) or soup.find(attrs={"itemprop": "author"})
                or soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
                or soup.find(class_=_AUTHOR_CLASS) or any(_schema.has(i, "author") for i in items))


def _has_date(pg, items) -> bool:
    soup = pg.soup
    return bool(soup.find("time", attrs={"datetime": True})
                or soup.find("meta", attrs={"property": re.compile("^article:(published|modified)_time$", re.I)})
                or any(_schema.has(i, "datePublished") or _schema.has(i, "dateModified") for i in items))


@check("SEO-EEA-001",
       title="Vertrauenssignale (E-E-A-T-Indizien) ## Trust signals (E-E-A-T indications)",
       why="Google beschreibt Erfahrung, Fachwissen, Autorität und Vertrauen (E-E-A-T) als Qualitätsmerkmal. Es gibt keinen "
           "technischen Messwert dafür, aber sichtbare Signale wie Über-uns-Seite, Kontakt, Impressum, Autorenangabe und "
           "Datum helfen Besuchern und Bewertern. ## Google describes experience, expertise, authoritativeness and trust "
           "(E-E-A-T) as a quality criterion. There is no technical metric for it, but visible signals such as an about page, "
           "contact, legal notice, author byline and date help visitors and raters.",
       method="Sucht in den Links aller gecrawlten Seiten nach Über-uns, Kontakt und Impressum und prüft auf Seiten mit "
              "mindestens 400 Wörtern, ob Autor und Datum angegeben sind (rel=author, itemprop, meta, time, Schema.org). Das "
              "sind Indizien aus dem HTML, keine Bewertung. ## Looks in the links of all crawled pages for about, contact and "
              "legal notice and checks on pages with at least 400 words whether author and date are given (rel=author, "
              "itemprop, meta, time, Schema.org). These are indications from the HTML, not a rating.",
       logic="Nur Info: ein Befund mit der Liste der nicht gefundenen Signale. ## Info only: one finding with the list of signals "
             "not found.",
       fix="Über-uns- und Kontaktseite verlinken, Autoren mit Kurzprofil und Veröffentlichungsdatum angeben. ## Link an about "
           "and a contact page, give authors with a short profile and the publication date.",
       refs=[GOOGLE + "fundamentals/creating-helpful-content", "https://developers.google.com/search/blog/2022/12/google-raters-guidelines-e-e-a-t"],
       profiles="sd")
def trust_signals(snap):
    docs = snap.docs()
    if not docs:
        return []
    about = contact = legal = False
    long_pages = authored = dated = 0
    for pg in docs:
        for text in _anchor_texts(pg):
            about = about or bool(_ABOUT.search(text))
            contact = contact or bool(_CONTACT.search(text))
            legal = legal or bool(_LEGAL.search(text))
        if len(_words(pg)) >= 400:
            long_pages += 1
            items = _schema.items(pg)
            authored += _has_author(pg, items)
            dated += _has_date(pg, items)
    missing_de, missing_en = [], []
    for found, de, en in ((about, "Über-uns-Seite", "about page"), (contact, "Kontaktseite", "contact page"),
                          (legal, "Impressum", "legal notice")):
        if not found:
            missing_de.append(de)
            missing_en.append(en)
    if long_pages and not authored:
        missing_de.append("Autorenangabe")
        missing_en.append("author byline")
    if long_pages and not dated:
        missing_de.append("Datumsangabe")
        missing_en.append("date")
    if not missing_de:
        return []
    return [F("SEO-EEA-001", S.INFO, snap.target.url,
              f"Vertrauenssignale nicht gefunden: {', '.join(missing_de)} (nur Indizien)",
              f"Trust signals not found: {', '.join(missing_en)} (indications only)")]


@check("SEO-GEO-001",
       title="Struktur für KI-Antworten (GEO) ## Structure for AI answers (GEO)",
       why="KI-Suchen und Antwortmaschinen übernehmen Inhalte leichter, wenn sie klar gegliedert sind: Fragen mit Antworten, "
           "Listen, Tabellen und eindeutige Angaben, wer hinter der Website steht. Wie stark das wirkt, ist offen. ## AI search "
           "and answer engines take over content more easily if it is clearly structured: questions with answers, lists, tables "
           "and clear information about who is behind the website. How strong the effect is remains open.",
       method="Prüft drei Strukturmerkmale: Überschriften (h2, h3) in Frageform ohne FAQPage-Daten, Seiten mit mindestens 600 "
              "Wörtern ohne Zwischenüberschriften, Listen oder Tabellen, und eine Startseite ohne Organization-, WebSite- oder "
              "Person-Daten. Das sind Heuristiken, kein belegter Rankingfaktor. ## Checks three structure features: headings "
              "(h2, h3) in question form without FAQPage data, pages with at least 600 words without subheadings, lists or "
              "tables, and a home page without Organization, WebSite or Person data. These are heuristics, not a proven ranking "
              "factor.",
       logic="Nur Info. ## Info only.",
       fix="Fragen als Überschrift mit kurzer Antwort darunter schreiben und mit FAQPage auszeichnen, lange Texte mit "
           "Zwischenüberschriften und Listen gliedern, Organization-Daten auf der Startseite einbinden. ## Write questions as "
           "headings with a short answer below and mark them up with FAQPage, split long texts with subheadings and lists, add "
           "Organization data on the home page.",
       refs=[GOOGLE + "appearance/structured-data/faqpage", SCHEMA + "Organization"], profiles="sd")
def ai_structure(snap):
    docs = snap.docs()
    if not docs:
        return []
    questions, unstructured = [], []
    for pg in docs:
        items = _schema.items(pg)
        heads = pg.soup.find_all(["h2", "h3"], limit=200)
        asks = [h for h in heads if h.get_text(strip=True).endswith(("?", "？"))]
        if asks and not any("faqpage" in _schema.types_of(i) for i in items):
            questions.append(pg.url)
        if (len(_words(pg)) >= 600 and not pg.soup.find(["ul", "ol", "table"])
                and len(pg.soup.find_all("h2", limit=3)) < 2):
            unstructured.append(pg.url)
    out = []
    if questions:
        out.append(F("SEO-GEO-001", S.INFO, questions[0],
                     f"{len(questions)} Seite(n) mit Überschriften in Frageform, aber ohne FAQPage-Daten",
                     f"{len(questions)} page(s) with question headings but without FAQPage data"))
    if unstructured:
        out.append(F("SEO-GEO-001", S.INFO, unstructured[0],
                     f"{len(unstructured)} Seite(n) mit viel Text, aber ohne Zwischenüberschriften, Listen oder Tabellen",
                     f"{len(unstructured)} page(s) with a lot of text but without subheadings, lists or tables"))
    entity = {"organization", "website", "person"} | _schema.LOCAL_TYPES
    if not any(_schema.types_of(i) & entity for i in _schema.items(docs[0])):
        out.append(F("SEO-GEO-001", S.INFO, docs[0].url,
                     "Startseite ohne Organization-, WebSite- oder Person-Daten (wer steckt dahinter?)",
                     "Home page without Organization, WebSite or Person data (who is behind it?)"))
    return out


@check("SEO-LOC-001",
       title="Lokales SEO (Firmendaten) ## Local SEO (business data)",
       why="Für lokale Suchen (Karten, Öffnungszeiten, Anrufen) braucht Google eindeutige Firmendaten: Name, Adresse und "
           "Telefonnummer müssen überall gleich sein. ## For local searches (maps, opening hours, calling) Google needs "
           "unambiguous business data: name, address and phone number must be the same everywhere.",
       method="Wertet LocalBusiness-Daten (auch Untertypen wie Restaurant oder Dentist) aus: Pflichtfelder name, address, "
              "telephone, die Teile der Adresse und empfohlene Felder (Öffnungszeiten, geo, image). Ohne solche Daten wird "
              "nur gemeldet, wenn Telefon-Links und ein address-Element vorkommen. Mehr als zwei verschiedene Telefonnummern "
              "weisen auf uneinheitliche Angaben hin. ## Evaluates LocalBusiness data (also subtypes such as Restaurant or "
              "Dentist): required fields name, address, telephone, the parts of the address and recommended fields (opening "
              "hours, geo, image). Without such data it only reports when phone links and an address element occur. More than "
              "two different phone numbers hint at inconsistent data.",
       logic="Pflichtfelder oder Adressteile fehlen: Hinweis. Empfohlene Felder fehlen, Kontaktdaten ohne Markup oder viele "
             "Nummern: Info. ## Required fields or address parts missing: note. Recommended fields missing, contact data "
             "without markup or many numbers: info.",
       fix="LocalBusiness-JSON-LD mit Name, vollständiger Adresse, Telefon, Öffnungszeiten und Koordinaten einbinden. ## Add "
           "LocalBusiness JSON-LD with name, full address, phone, opening hours and coordinates.",
       refs=[GOOGLE + "appearance/structured-data/local-business", SCHEMA + "LocalBusiness"], profiles="sd")
def local_seo(snap):
    locals_, phones, has_address = [], set(), False
    for pg in snap.docs():
        for item in _schema.items(pg):
            if _schema.types_of(item) & _schema.LOCAL_TYPES:
                locals_.append((pg.url, item))
        for a in pg.soup.find_all("a", href=True, limit=500):
            href = str(a["href"]).strip().lower()
            if href.startswith("tel:"):
                digits = re.sub(r"\D", "", href[4:])
                if len(digits) >= 6:
                    phones.add(digits[-8:])
        has_address = has_address or bool(pg.soup.find("address") or pg.soup.find(attrs={"itemprop": "streetAddress"}))
    out = []
    if locals_:
        required, parts, recommended = set(), set(), set()
        for _url, item in locals_:
            required.update(p for p in ("name", "address", "telephone") if not _schema.has(item, p))
            address = item.get("address")
            if isinstance(address, dict):
                parts.update(p for p in ("streetAddress", "postalCode", "addressLocality") if not _schema.has(address, p))
            if not (_schema.has(item, "openingHoursSpecification") or _schema.has(item, "openingHours")):
                recommended.add("openingHours")
            recommended.update(p for p in ("geo", "image") if not _schema.has(item, p))
        first = locals_[0][0]
        if required or parts:
            missing = sorted(required) + sorted(f"address.{p}" for p in parts)
            out.append(F("SEO-LOC-001", S.NOTE, first, f"LocalBusiness-Daten unvollständig: es fehlen {', '.join(missing)}",
                         f"LocalBusiness data incomplete: missing {', '.join(missing)}"))
        if recommended:
            out.append(F("SEO-LOC-001", S.INFO, first,
                         f"LocalBusiness-Daten: empfohlene Felder fehlen: {', '.join(sorted(recommended))}",
                         f"LocalBusiness data: recommended fields missing: {', '.join(sorted(recommended))}"))
    elif phones and has_address:
        out.append(F("SEO-LOC-001", S.INFO, snap.target.url,
                     "Telefon und Adresse gefunden, aber keine LocalBusiness-Daten",
                     "Phone and address found, but no LocalBusiness data"))
    if len(phones) > 2:
        out.append(F("SEO-LOC-001", S.INFO, snap.target.url,
                     f"{len(phones)} verschiedene Telefonnummern auf der Website (Angaben einheitlich?)",
                     f"{len(phones)} different phone numbers on the website (consistent data?)"))
    return out


_CART = re.compile(r"(in den warenkorb|warenkorb|add to cart|add to basket|zur kasse|checkout|buy now|jetzt kaufen)", re.I)
_TERMS = re.compile(r"(agb|terms|bedingungen)", re.I)
_RETURNS = re.compile(r"(widerruf|return|retour|rückgabe|rueckgabe|refund)", re.I)
_SHIPPING = re.compile(r"(versand|shipping|lieferung|delivery)", re.I)


def _is_shop(pg, items) -> bool:
    if any("product" in _schema.types_of(i) for i in items) or pg.soup.find(attrs={"itemprop": "price"}):
        return True
    for element in pg.soup.find_all(["button", "a", "input"], limit=400):
        text = element.get_text(" ", strip=True) or str(element.get("value") or element.get("aria-label") or "")
        if _CART.search(text):
            return True
    return False


@check("SEO-ECO-001",
       title="Online-Shop: Produktdaten und Pflichtseiten ## Online shop: product data and required pages",
       why="Shops brauchen vollständige Produktdaten für Preis- und Bestandsanzeigen in der Suche und gut auffindbare "
           "Informationen zu AGB, Widerruf und Versand. Bewertungsdaten ohne Anzahl werden von Google ignoriert. ## Shops need "
           "complete product data for price and stock displays in search and easy-to-find information on terms, returns and "
           "shipping. Rating data without a count is ignored by Google.",
       method="Erkennt einen Shop an Product-Daten, itemprop=price oder Warenkorb-Schaltflächen. Prüft dann Product-Daten auf "
              "brand, sku oder gtin, gültige Währung (drei Großbuchstaben) und aggregateRating mit Wert und Anzahl sowie Links auf "
              "AGB, Widerruf oder Rückgabe und Versand. Hinweis, keine Rechtsberatung. ## Detects a shop by Product data, "
              "itemprop=price or cart buttons. Then checks Product data for brand, sku or gtin, a valid currency (three "
              "uppercase letters) and aggregateRating with value and count, plus links to terms, returns or withdrawal and "
              "shipping. Hint, not legal advice.",
       logic="Ungültige Währung oder Bewertung ohne Anzahl: Hinweis. Fehlende Marke oder Kennung, fehlende Links: Info. Kein "
             "Shop erkannt: kein Befund. ## Invalid currency or rating without a count: note. Missing brand or identifier, "
             "missing links: info. No shop detected: no finding.",
       fix="Product-Daten vervollständigen, Währung als ISO-Code angeben und AGB, Widerruf und Versand aus Menü oder Fußzeile "
           "verlinken. ## Complete the Product data, give the currency as an ISO code and link terms, returns and shipping "
           "from the menu or footer.",
       refs=[GOOGLE + "appearance/structured-data/product", SCHEMA + "Product"], profiles="sd")
def shop_quality(snap):
    shop, terms, returns, shipping = False, False, False, False
    bad_currency, bad_rating, no_ident = [], [], []
    for pg in snap.docs():
        items = _schema.items(pg)
        shop = _is_shop(pg, items) or shop
        for text in _anchor_texts(pg):
            terms = terms or bool(_TERMS.search(text))
            returns = returns or bool(_RETURNS.search(text))
            shipping = shipping or bool(_SHIPPING.search(text))
        for item in items:
            if "product" not in _schema.types_of(item):
                continue
            if not any(_schema.has(item, p) for p in ("brand", "sku", "gtin", "gtin13", "gtin8", "mpn")):
                no_ident.append(pg.url)
            currency = _schema.first_dict(item.get("offers")).get("priceCurrency")
            if currency is not None and not re.fullmatch(r"[A-Z]{3}", str(currency)):
                bad_currency.append(pg.url)
            rating = _schema.first_dict(item.get("aggregateRating"))
            if rating and not (_schema.has(rating, "ratingValue")
                               and (_schema.has(rating, "reviewCount") or _schema.has(rating, "ratingCount"))):
                bad_rating.append(pg.url)
    if not shop:
        return []
    out = []
    if bad_currency:
        out.append(F("SEO-ECO-001", S.NOTE, bad_currency[0], "Product-Daten mit ungültiger Währung (ISO-Code erwartet)",
                     "Product data with an invalid currency (ISO code expected)"))
    if bad_rating:
        out.append(F("SEO-ECO-001", S.NOTE, bad_rating[0], "aggregateRating ohne Wert oder ohne Anzahl der Bewertungen",
                     "aggregateRating without a value or without the number of ratings"))
    if no_ident:
        out.append(F("SEO-ECO-001", S.INFO, no_ident[0], f"{len(set(no_ident))} Product-Eintrag/Einträge ohne brand, sku oder gtin",
                     f"{len(set(no_ident))} Product entry/entries without brand, sku or gtin"))
    missing_de, missing_en = [], []
    for found, de, en in ((terms, "AGB", "terms"), (returns, "Widerruf oder Rückgabe", "returns or withdrawal"),
                          (shipping, "Versand", "shipping")):
        if not found:
            missing_de.append(de)
            missing_en.append(en)
    if missing_de:
        out.append(F("SEO-ECO-001", S.INFO, snap.target.url,
                     f"Shop erkannt, aber keine Links gefunden auf: {', '.join(missing_de)}",
                     f"Shop detected, but no links found to: {', '.join(missing_en)}"))
    return out
