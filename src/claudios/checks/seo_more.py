"""Weitere SEO-Prüfungen: hreflang, Open Graph, strukturierte Daten, Sitemap, Soft-404."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from publicsuffix2 import get_sld

from ..core.crawler import norm
from ..core.registry import check
from ._util import CheckSkipped, F, S

GOOGLE = "https://developers.google.com/search/docs/"
_LANG = re.compile(r"^(x-default|[a-z]{2,3}(-[a-z]{4})?(-([a-z]{2}|\d{3}))?)$", re.I)
_OG_REQUIRED = ("og:title", "og:description", "og:image")


def _noindex(pg) -> bool:
    meta = pg.soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    value = (str(meta.get("content", "")) if meta else "") + " " + pg.headers.get("x-robots-tag", "")
    return "noindex" in value.lower()


def _alternates(pg) -> list[tuple[str, str]]:
    out = []
    for link in pg.soup.find_all("link", href=True):
        rels = [r.lower() for r in (link.get("rel") or [])]
        if "alternate" in rels and link.get("hreflang"):
            out.append((str(link["hreflang"]).strip(), norm(urljoin(pg.url, str(link["href"]).strip()))))
    return out


@check("SEO-HRF-001",
       title="hreflang (Sprachversionen) ## hreflang (language versions)",
       why="Bei mehrsprachigen Seiten sagt hreflang den Suchmaschinen, welche Version zu welcher Sprache gehört. "
           "Fehlen die Gegenverweise oder stimmen die Sprachcodes nicht, ignoriert Google die Angaben und zeigt "
           "womöglich die falsche Sprache. ## On multilingual sites hreflang tells search engines which "
           "version belongs to which language. If the return links are missing or the language codes are "
           "wrong, Google ignores the annotations and may show the wrong language.",
       method="Liest link rel=alternate hreflang auf allen gecrawlten Seiten, prüft die Sprachcodes, den "
              "Verweis auf sich selbst und ob jede gecrawlte Zielseite zurückverweist. Ohne hreflang wird nur "
              "geprüft, ob die gecrawlten Seiten verschiedene lang-Werte haben. ## Reads link rel=alternate "
              "hreflang on all crawled pages, checks the language codes, the self reference and whether every "
              "crawled target page links back. Without hreflang it only checks whether the crawled pages have "
              "different lang values.",
       logic="Ungültiger Code oder fehlender Rückverweis: Warnung. Fehlender Selbstverweis oder mehrere Sprachen "
             "ohne hreflang: Hinweis. Fehlendes x-default: Info. ## Invalid code or missing return link: "
             "warning. Missing self reference or several languages without hreflang: note. Missing x-default: "
             "info.",
       fix="Jede Sprachversion verweist auf alle Versionen einschließlich sich selbst, zum Beispiel "
           "<link rel=\"alternate\" hreflang=\"de\" href=\"...\">, plus x-default. ## Every language version "
           "links to all versions including itself, for example <link rel=\"alternate\" hreflang=\"en\" "
           "href=\"...\">, plus x-default.",
       refs=[GOOGLE + "specialty/international/localized-versions", "https://www.rfc-editor.org/rfc/rfc5646"],
       profiles="sd")
def hreflang(snap):
    pages = {norm(p.url): p for p in snap.docs()}
    alts = {key: _alternates(p) for key, p in pages.items()}
    out = []
    if not any(alts.values()):
        langs = set()
        for pg in pages.values():
            root = pg.soup.find("html")
            code = str(root.get("lang", "")).strip().lower().split("-")[0] if root else ""
            if code:
                langs.add(code)
        if len(langs) > 1:
            out.append(F("SEO-HRF-001", S.NOTE, snap.target.url,
                         "Mehrere Sprachen gefunden, aber kein hreflang gesetzt",
                         "Several languages found but no hreflang set", ", ".join(sorted(langs))))
        return out
    for key, entries in alts.items():
        if not entries:
            continue
        url = pages[key].url
        bad = sorted({code for code, _target in entries if not _LANG.match(code)})
        if bad:
            out.append(F("SEO-HRF-001", S.WARNING, url, "Ungültiger hreflang-Sprachcode",
                         "Invalid hreflang language code", ", ".join(bad)[:80]))
        targets = {target for _code, target in entries}
        if key not in targets:
            out.append(F("SEO-HRF-001", S.NOTE, url, "hreflang ohne Verweis auf die Seite selbst",
                         "hreflang without a reference to the page itself"))
        if not any(code.lower() == "x-default" for code, _target in entries):
            out.append(F("SEO-HRF-001", S.INFO, url, "hreflang ohne x-default", "hreflang without x-default"))
        for target in sorted(targets):
            if target == key or target not in alts:
                continue
            if key not in {back for _code, back in alts[target]}:
                out.append(F("SEO-HRF-001", S.WARNING, url, "hreflang ohne Rückverweis der Zielseite",
                             "hreflang target page has no return link", target[:100]))
    return out


@check("SEO-SOC-001",
       title="Open Graph und Twitter Cards ## Open Graph and Twitter Cards",
       why="Open-Graph- und Twitter-Card-Angaben steuern Titel, Beschreibung und Bild, wenn eine Seite in sozialen "
           "Netzwerken oder Messengern geteilt wird. Ohne sie wählen die Dienste oft unpassende Vorschauen. ## "
           "Open Graph and Twitter Card tags control title, description and image when a page is shared on "
           "social networks or messengers. Without them the services often pick unsuitable previews.",
       method="Prüft je Seite og:title, og:description und og:image, ob og:image eine absolute Adresse ist, und "
              "auf der Startseite zusätzlich twitter:card. ## Checks per page og:title, og:description and "
              "og:image, whether og:image is an absolute address, and on the start page also twitter:card.",
       logic="Fehlende Angaben auf der Startseite oder relatives Bild: Hinweis. Fehlende Angaben auf "
             "Unterseiten und fehlende twitter:card: Info. ## Missing tags on the start page or relative "
             "image: note. Missing tags on sub pages and missing twitter:card: info.",
       fix="Im head meta property=\"og:title\", \"og:description\", \"og:image\" (absolute Adresse) und "
           "name=\"twitter:card\" setzen. ## Set meta property=\"og:title\", \"og:description\", \"og:image\" "
           "(absolute address) and name=\"twitter:card\" in the head.",
       refs=["https://ogp.me/", "https://developer.x.com/en/docs/x-for-websites/cards/overview/abouts-cards"],
       profiles="sd")
def social(snap):
    out = []
    start = snap.pages[0] if snap.pages else None
    for pg in snap.docs():
        props: dict[str, str] = {}
        for meta in pg.soup.find_all("meta"):
            key = str(meta.get("property") or meta.get("name") or "").strip().lower()
            if key.startswith(("og:", "twitter:")) and key not in props:
                props[key] = str(meta.get("content", "")).strip()
        missing = [k for k in _OG_REQUIRED if not props.get(k)]
        if missing:
            listed = ", ".join(missing)
            out.append(F("SEO-SOC-001", S.NOTE if pg is start else S.INFO, pg.url,
                         f"Open Graph unvollständig, es fehlt: {listed}",
                         f"Open Graph incomplete, missing: {listed}"))
        image = props.get("og:image", "")
        if image and not image.lower().startswith(("https:", "http:")):
            out.append(F("SEO-SOC-001", S.NOTE, pg.url, "og:image ist keine absolute Adresse",
                         "og:image is not an absolute address", image[:80]))
        if pg is start and "twitter:card" not in props:
            out.append(F("SEO-SOC-001", S.INFO, pg.url, "twitter:card fehlt", "twitter:card missing"))
    return out


def _items(data) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            return [x for x in graph if isinstance(x, dict)]
        return [data]
    return []


@check("SEO-STR-001",
       title="Strukturierte Daten (JSON-LD) ## Structured data (JSON-LD)",
       why="Strukturierte Daten sind die Voraussetzung für Rich Results wie Sterne, Preise oder Veranstaltungen "
           "in der Suche. Fehlerhaftes JSON oder fehlende Pflichtangaben werden von Google einfach ignoriert. ## "
           "Structured data is the prerequisite for rich results such as stars, prices or events in search. "
           "Faulty JSON or missing required fields are simply ignored by Google.",
       method="Liest alle JSON-LD-Blöcke, prüft die JSON-Syntax sowie @context (schema.org) und @type. Die "
              "schema.org-Typen und ihre Pflichtfelder werden nicht geprüft. Mikrodaten (itemscope) zählen "
              "als vorhanden. ## Reads all JSON-LD blocks and checks the JSON syntax as well as @context "
              "(schema.org) and @type. The schema.org types and their required fields are not validated. "
              "Microdata (itemscope) counts as present.",
       logic="Ungültiges JSON, fehlender @context oder @type: Warnung. Keine strukturierten Daten auf der "
             "Startseite: Info. ## Invalid JSON, missing @context or @type: warning. No structured data on the "
             "start page: info.",
       fix="JSON-LD mit \"@context\": \"https://schema.org\" und passendem \"@type\" einbinden und im Rich-Results-Test "
           "von Google prüfen. ## Add JSON-LD with \"@context\": \"https://schema.org\" and a matching \"@type\" "
           "and verify it in Google's Rich Results Test.",
       refs=[GOOGLE + "appearance/structured-data/intro-structured-data", "https://schema.org/docs/gs.html"],
       profiles="sd")
def structured(snap):
    out = []
    start = snap.pages[0] if snap.pages else None
    start_has = False
    for pg in snap.docs():
        soup = pg.soup
        blocks = soup.find_all("script", attrs={"type": re.compile(r"^application/ld\+json$", re.I)})
        micro = soup.find(attrs={"itemscope": True}) is not None
        if (blocks or micro) and pg is start:
            start_has = True
        for block in blocks:
            raw = block.string or block.get_text()
            try:
                data = json.loads(raw)
            except ValueError:
                out.append(F("SEO-STR-001", S.WARNING, pg.url, "JSON-LD enthält ungültiges JSON",
                             "JSON-LD contains invalid JSON", raw.strip()[:60]))
                continue
            top_context = data.get("@context") if isinstance(data, dict) else None
            for item in _items(data):
                context = item.get("@context", top_context)
                if "schema.org" not in str(context).lower():
                    out.append(F("SEO-STR-001", S.WARNING, pg.url, "JSON-LD ohne @context schema.org",
                                 "JSON-LD without @context schema.org"))
                if not item.get("@type") and "@graph" not in item:
                    out.append(F("SEO-STR-001", S.WARNING, pg.url, "JSON-LD-Eintrag ohne @type",
                                 "JSON-LD item without @type"))
    if start is not None and start.html is not None and not start_has:
        out.append(F("SEO-STR-001", S.INFO, start.url, "Keine strukturierten Daten auf der Startseite",
                     "No structured data on the start page"))
    return out


@check("SEO-SMP-001",
       title="Sitemap ## Sitemap",
       why="Die Sitemap hilft Suchmaschinen, alle wichtigen Seiten zu finden. Enthält sie Fehlerseiten, "
           "Weiterleitungen oder noindex-Seiten, verliert sie an Glaubwürdigkeit, und neue Seiten werden "
           "später entdeckt. ## The sitemap helps search engines find all important pages. If it contains "
           "error pages, redirects or noindex pages it loses credibility and new pages are discovered later.",
       method="Sucht eine Sitemap über die Zeile Sitemap in der robots.txt oder unter /sitemap.xml. Liest "
              "höchstens 2.000 Adressen (bei einem Index nur die erste Unter-Sitemap), gleicht sie mit den "
              "gecrawlten Seiten ab und prüft bis zu 20 nicht gecrawlte Adressen per HEAD. Komprimierte "
              "Sitemaps (.gz) werden nicht gelesen. ## Looks for a sitemap via the Sitemap line in robots.txt "
              "or at /sitemap.xml. Reads at most 2,000 addresses (only the first child sitemap of an index), "
              "compares them with the crawled pages and checks up to 20 uncrawled addresses via HEAD. "
              "Compressed sitemaps (.gz) are not read.",
       logic="Adresse mit HTTP-Fehler, noindex oder http-Adresse: Fehler beziehungsweise Warnung. Keine Sitemap, "
             "Weiterleitung, fremde Domain: Hinweis. Nicht in robots.txt eingetragen oder gecrawlte Seiten "
             "fehlen: Info. ## Address with HTTP error: error, noindex or http address: warning. No "
             "sitemap, redirect, foreign domain: note. Not listed in robots.txt or crawled pages missing: info.",
       fix="Sitemap mit nur indexierbaren Seiten (Status 200) unter /sitemap.xml bereitstellen und in der "
           "robots.txt mit 'Sitemap: https://domain/sitemap.xml' eintragen. ## Provide a sitemap with only "
           "indexable pages (status 200) at /sitemap.xml and list it in robots.txt with 'Sitemap: "
           "https://domain/sitemap.xml'.",
       refs=[GOOGLE + "crawling-indexing/sitemaps/overview", "https://www.sitemaps.org/protocol.html"],
       profiles="sd", source="network")
def sitemap(snap):
    data = snap.extra.get("sitemap")
    if data is None:
        raise CheckSkipped("no_sitemap_data")
    url = snap.target.url
    if not data["found"]:
        if not data["reachable"]:
            raise CheckSkipped("sitemap_unreachable")
        return [F("SEO-SMP-001", S.NOTE, url, "Keine Sitemap gefunden (weder in der robots.txt noch unter /sitemap.xml)",
                  "No sitemap found (neither in robots.txt nor at /sitemap.xml)")]
    out = []
    if not data["declared"]:
        out.append(F("SEO-SMP-001", S.INFO, url, "Sitemap ist nicht in der robots.txt eingetragen",
                     "Sitemap is not listed in robots.txt"))
    urls = data["urls"]
    if not urls:
        if data["child_failed"]:
            out.append(F("SEO-SMP-001", S.NOTE, url, "Sitemap-Index: die Unter-Sitemap ist nicht abrufbar",
                         "Sitemap index: the child sitemap is not reachable"))
        else:
            out.append(F("SEO-SMP-001", S.WARNING, url, "Die Sitemap enthält keine Adressen",
                         "The sitemap contains no addresses"))
        return out
    insecure = [u for u in urls if u.lower().startswith("http:")]
    if insecure:
        out.append(F("SEO-SMP-001", S.WARNING, url, f"{len(insecure)} Sitemap-Adresse(n) ohne HTTPS",
                     f"{len(insecure)} sitemap address(es) without HTTPS", insecure[0][:100]))
    foreign = [u for u in urls if (get_sld((re.sub(r"^[a-z]+:/*", "", u.lower()).split("/")[0].split(":")[0]))
                                   or "") != snap.target.registrable]
    if foreign:
        out.append(F("SEO-SMP-001", S.NOTE, url, f"{len(foreign)} Sitemap-Adresse(n) einer anderen Domain",
                     f"{len(foreign)} sitemap address(es) of another domain", foreign[0][:100]))
    listed = {norm(u) for u in urls}
    for pg in snap.pages:
        keys = {norm(pg.url), *(norm(u) for u in pg.chain)}
        if not listed & keys:
            continue
        if pg.status is not None and pg.status >= 400:
            out.append(F("SEO-SMP-001", S.ERROR, pg.url, f"Sitemap-Adresse liefert HTTP {pg.status}",
                         f"Sitemap address returns HTTP {pg.status}"))
        elif norm(pg.url) not in listed:
            out.append(F("SEO-SMP-001", S.NOTE, pg.url, "Sitemap-Adresse leitet weiter",
                         "Sitemap address redirects"))
        elif pg.html is not None and _noindex(pg):
            out.append(F("SEO-SMP-001", S.WARNING, pg.url, "Sitemap enthält eine noindex-Seite",
                         "Sitemap contains a noindex page"))
    for rec in data["checked"]:
        if rec["error"]:
            out.append(F("SEO-SMP-001", S.WARNING, rec["url"], "Sitemap-Adresse nicht erreichbar",
                         "Sitemap address unreachable"))
        elif rec["status"] is not None and rec["status"] >= 400:
            out.append(F("SEO-SMP-001", S.ERROR, rec["url"], f"Sitemap-Adresse liefert HTTP {rec['status']}",
                         f"Sitemap address returns HTTP {rec['status']}"))
        elif rec["redirects"]:
            out.append(F("SEO-SMP-001", S.NOTE, rec["url"], "Sitemap-Adresse leitet weiter",
                         "Sitemap address redirects"))
    if not data["index"] and not data["truncated"]:
        missing = []
        for pg in snap.docs():
            keys = {norm(pg.url), *(norm(u) for u in pg.chain)}
            if pg.status == 200 and "?" not in pg.url and not listed & keys and not _noindex(pg):
                missing.append(pg.url)
        if missing:
            out.append(F("SEO-SMP-001", S.INFO, missing[0], f"{len(missing)} gecrawlte Seite(n) fehlen in der Sitemap",
                         f"{len(missing)} crawled page(s) missing from the sitemap"))
    return out


@check("SEO-SFT-001",
       title="Soft-404 (Fehlerseiten mit Status 200) ## Soft 404 (error pages with status 200)",
       why="Liefert eine nicht existierende Adresse den Status 200 statt 404, behandeln Suchmaschinen die "
           "Fehlerseite als echte Seite. Das verschwendet Crawl-Budget und füllt den Index mit wertlosen "
           "Treffern. ## If a non-existent address returns status 200 instead of 404, search engines treat "
           "the error page as a real page. This wastes crawl budget and fills the index with worthless results.",
       method="Ruft genau eine zufällige, nicht existierende Adresse auf (/claudios-check-<zufall>) und "
              "wertet den Statuscode aus. ## Requests exactly one random non-existent address "
              "(/claudios-check-<random>) and evaluates the status code.",
       logic="HTTP 200 (auch nach Weiterleitung): Warnung. HTTP 5xx: Warnung. 401, 403 oder 429: Info. 404 oder "
             "410: in Ordnung. ## HTTP 200 (also after a redirect): warning. HTTP 5xx: warning. 401, 403 or "
             "429: info. 404 or 410: fine.",
       fix="Für unbekannte Adressen den Status 404 oder 410 senden und Fehlerseiten nicht auf die Startseite "
           "weiterleiten. ## Send status 404 or 410 for unknown addresses and do not redirect error pages "
           "to the home page.",
       refs=[GOOGLE + "crawling-indexing/http-network-errors", "https://www.rfc-editor.org/rfc/rfc9110.html"],
       profiles="sd", source="network")
def soft404(snap):
    rec = snap.extra.get("soft404")
    if rec is None:
        raise CheckSkipped("no_soft404_data")
    if rec["error"] or rec["status"] is None:
        raise CheckSkipped("soft404_unreachable")
    status, url = rec["status"], snap.target.url
    if status == 200:
        if rec["redirects"]:
            return [F("SEO-SFT-001", S.WARNING, url, "Unbekannte Adresse wird weitergeleitet und liefert dann HTTP 200 (Soft-404)",
                      "Unknown address is redirected and then returns HTTP 200 (soft 404)", str(rec["final"])[:100])]
        return [F("SEO-SFT-001", S.WARNING, url, "Unbekannte Adresse liefert HTTP 200 statt 404 (Soft-404)",
                  "Unknown address returns HTTP 200 instead of 404 (soft 404)")]
    if status >= 500:
        return [F("SEO-SFT-001", S.WARNING, url, f"Unbekannte Adresse führt zu einem Serverfehler (HTTP {status})",
                  f"Unknown address causes a server error (HTTP {status})")]
    if status in (401, 403, 429):
        return [F("SEO-SFT-001", S.INFO, url, f"Der Server verweigerte den Test (HTTP {status})",
                  f"The server refused the test (HTTP {status})")]
    return []