"""Weitere SEO- und Auslieferungs-Prüfungen: Kompression, Caching, dünne Inhalte, URL-Struktur, Klicktiefe,
robots.txt-Tiefe und Favicon. Außer dem Favicon (Probe core/probe_passive.py) werten sie nur den Snapshot aus."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlsplit

from bs4 import Comment

from ..core.limits import LIMITS
from ..core.registry import check
from ._util import CheckSkipped, F, S

GOOGLE = "https://developers.google.com/search/docs/"
_ENCODINGS = ("gzip", "br", "zstd", "deflate", "compress")
_VALIDATORS = ("cache-control", "etag", "last-modified", "expires")
_SKIP_PARENTS = {"script", "style", "noscript", "template", "head", "title"}
_SESSION_PARAMS = {"phpsessid", "jsessionid", "sessionid", "sid", "session_id", "sessid", "aspsessionid"}
_ASSET_RULE = re.compile(r"\.(css|js)($|[$*?])")
_ASSET_DIRS = {"/js", "/css", "/assets", "/static", "/wp-includes"}
_KNOWN_AGENTS = {"googlebot", "bingbot"}


def _noindex(pg) -> bool:
    meta = pg.soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    value = (str(meta.get("content", "")) if meta else "") + " " + pg.headers.get("x-robots-tag", "")
    return "noindex" in value.lower()


def _has_password(pg) -> bool:
    return pg.soup.find("input", attrs={"type": re.compile("^password$", re.I)}) is not None


@check("SEO-CMP-001",
       title="Komprimierung der HTML-Seiten ## Compression of HTML pages",
       why="Ohne gzip oder Brotli sind HTML-Seiten drei- bis zehnmal größer als nötig. Das verlangsamt das Laden, "
           "kostet mobile Besucher Datenvolumen und belastet den Server. ## Without gzip or Brotli HTML pages are "
           "three to ten times larger than necessary. This slows loading, costs mobile visitors data and burdens "
           "the server.",
       method="Prüft bei HTML-Seiten ab 1.500 Bytes den Header Content-Encoding (gzip, br, zstd, deflate). Skripte, "
              "Stile und Bilder werden hier nicht geprüft. ## Checks the Content-Encoding header (gzip, br, zstd, "
              "deflate) of HTML pages from 1,500 bytes. Scripts, styles and images are not checked here.",
       logic="Seiten ohne Komprimierung: Hinweis, bei Seiten über 100.000 Bytes Warnung. ## Pages without "
             "compression: note, warning for pages above 100,000 bytes.",
       fix="Auf dem Server gzip oder Brotli für text/html, CSS und JavaScript aktivieren. ## Enable gzip or Brotli on "
           "the server for text/html, CSS and JavaScript.",
       refs=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Compression", "https://web.dev/articles/reduce-network-payloads-using-text-compression"])
def compression(snap):
    docs = [pg for pg in snap.docs() if pg.size >= 1500]
    bad = [pg for pg in docs if not any(e in pg.headers.get("content-encoding", "").lower() for e in _ENCODINGS)]
    if not bad:
        return []
    heavy = any(pg.size > 100_000 for pg in bad)
    return [F("SEO-CMP-001", S.WARNING if heavy else S.NOTE, bad[0].url,
              f"{len(bad)} von {len(docs)} HTML-Seiten werden ohne Komprimierung ausgeliefert",
              f"{len(bad)} of {len(docs)} HTML pages are served without compression", f"{bad[0].size} Bytes")]


@check("SEO-CCH-001",
       title="Caching der HTML-Seiten ## Caching of HTML pages",
       why="Ohne Cache-Control, ETag oder Last-Modified können Browser und Suchmaschinen nicht nachfragen, ob sich "
           "eine Seite geändert hat. Jeder Abruf lädt die ganze Seite neu. ## Without Cache-Control, ETag or "
           "Last-Modified browsers and search engines cannot ask whether a page has changed. Every request loads "
           "the whole page again.",
       method="Prüft je HTML-Seite, ob mindestens einer der Header Cache-Control, ETag, Last-Modified oder Expires "
              "vorhanden ist, und zählt öffentliche Seiten mit no-store. Statische Dateien werden hier nicht "
              "geprüft. ## Checks per HTML page whether at least one of the headers Cache-Control, ETag, "
              "Last-Modified or Expires is present and counts public pages with no-store. Static files are not "
              "checked here.",
       logic="Seiten ganz ohne Cache-Header: Hinweis. Öffentliche Seiten mit no-store: Info. ## Pages without any "
             "cache header: note. Public pages with no-store: info.",
       fix="Mindestens ETag oder Last-Modified senden, dazu Cache-Control (zum Beispiel max-age=0, must-revalidate "
           "für HTML). ## Send at least ETag or Last-Modified plus Cache-Control (for example max-age=0, "
           "must-revalidate for HTML).",
       refs=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching", "https://web.dev/articles/http-cache"])
def caching(snap):
    docs = snap.docs()
    bare = [pg for pg in docs if not any(pg.headers.get(h) for h in _VALIDATORS)]
    nostore = [pg for pg in docs if "no-store" in pg.headers.get("cache-control", "").lower()
               and not _has_password(pg)]
    out = []
    if bare:
        out.append(F("SEO-CCH-001", S.NOTE, bare[0].url,
                     f"{len(bare)} von {len(docs)} HTML-Seiten ohne jeden Cache-Header",
                     f"{len(bare)} of {len(docs)} HTML pages without any cache header"))
    if nostore:
        out.append(F("SEO-CCH-001", S.INFO, nostore[0].url,
                     f"{len(nostore)} öffentliche Seite(n) mit Cache-Control: no-store",
                     f"{len(nostore)} public page(s) with Cache-Control: no-store"))
    return out


def _words(pg) -> list[str]:
    words: list[str] = []
    for string in pg.soup.find_all(string=True):
        if isinstance(string, Comment) or string.parent.name in _SKIP_PARENTS:
            continue
        words.extend(str(string).split())
        if len(words) > 20000:
            break
    return words


@check("SEO-THN-001",
       title="Dünne und doppelte Inhalte ## Thin and duplicate content",
       why="Seiten mit sehr wenig Text bieten Suchmaschinen kaum Anhaltspunkte, und Seiten mit identischem Text "
           "konkurrieren miteinander. Beides schwächt das Ranking. ## Pages with very little text give search "
           "engines hardly anything to go on, and pages with identical text compete with each other. Both weaken "
           "the ranking.",
       method="Zählt den gesamten sichtbaren Text jeder Seite (ohne Skripte, Stile und Kommentare, aber mit Menü und "
              "Fußzeile) und vergleicht Seiten ab 50 Wörtern per Prüfsumme. Seiten mit noindex bleiben außen vor. "
              "Seiten, die ihren Inhalt per JavaScript laden, wirken dünn. ## Counts all visible text of each page "
              "(without scripts, styles and comments, but including menu and footer) and compares pages from 50 "
              "words by checksum. Pages with noindex are left out. Pages that load their content by JavaScript "
              "look thin.",
       logic="Unter 50 Wörtern oder identischer Text auf mehreren Seiten: Hinweis. 50 bis 149 Wörter: Info. ## "
             "Below 50 words or identical text on several pages: note. 50 to 149 words: info.",
       fix="Seiten mit eigenem, hilfreichem Inhalt füllen, zusammenführen oder per noindex ausnehmen; doppelte "
           "Inhalte per Canonical bündeln. ## Fill pages with their own useful content, merge them or exclude them "
           "with noindex; consolidate duplicates with a canonical.",
       refs=[GOOGLE + "fundamentals/creating-helpful-content", GOOGLE + "crawling-indexing/consolidate-duplicate-urls"],
       profiles="sd")
def thin_content(snap):
    very, thin, seen = [], [], {}
    for pg in snap.docs():
        if _noindex(pg):
            continue
        words = _words(pg)
        if len(words) < 50:
            very.append(pg.url)
        else:
            if len(words) < 150:
                thin.append(pg.url)
            digest = hashlib.sha256(" ".join(words).lower().encode("utf-8")).hexdigest()
            seen.setdefault(digest, []).append(pg.url)
    out = []
    if very:
        out.append(F("SEO-THN-001", S.NOTE, very[0], f"{len(very)} Seite(n) mit weniger als 50 Wörtern",
                     f"{len(very)} page(s) with fewer than 50 words"))
    if thin:
        out.append(F("SEO-THN-001", S.INFO, thin[0], f"{len(thin)} Seite(n) mit 50 bis 149 Wörtern",
                     f"{len(thin)} page(s) with 50 to 149 words"))
    groups = [urls for urls in seen.values() if len(urls) > 1]
    if groups:
        pages = sum(len(urls) for urls in groups)
        out.append(F("SEO-THN-001", S.NOTE, groups[0][0], f"{len(groups)} Textgruppe(n) mit identischem Inhalt auf {pages} Seiten",
                     f"{len(groups)} text group(s) with identical content on {pages} pages"))
    return out


_URL_RULES = (
    ("session", S.WARNING, "Session-ID in der URL", "Session ID in the URL"),
    ("params", S.NOTE, "mehr als 3 Parameter in der URL", "more than 3 parameters in the URL"),
    ("long", S.NOTE, "URL länger als 115 Zeichen", "URL longer than 115 characters"),
    ("upper", S.NOTE, "Großbuchstaben im URL-Pfad", "Uppercase letters in the URL path"),
    ("space", S.NOTE, "Leerzeichen im URL-Pfad", "Spaces in the URL path"),
    ("double", S.NOTE, "doppelter Schrägstrich im URL-Pfad", "double slash in the URL path"),
    ("underscore", S.INFO, "Unterstrich im URL-Pfad (Bindestrich ist üblich)",
     "Underscore in the URL path (hyphens are the norm)"),
    ("deep", S.INFO, "mehr als 5 Pfadebenen", "more than 5 path levels"),
)


@check("SEO-URL-001",
       title="URL-Struktur ## URL structure",
       why="Kurze, sprechende URLs ohne Session-IDs und Parameterwust lassen sich besser teilen, crawlen und "
           "indexieren. Session-IDs erzeugen zahllose Duplikate derselben Seite. ## Short, readable URLs without "
           "session IDs and parameter clutter are easier to share, crawl and index. Session IDs create countless "
           "duplicates of the same page.",
       method="Wertet die Adressen aller gecrawlten HTML-Seiten aus: Länge, Großbuchstaben, Unterstriche, "
              "Leerzeichen, doppelte Schrägstriche, Parameter, Session-Parameter und Pfadtiefe. Je Regel ein "
              "Befund mit Anzahl. ## Evaluates the addresses of all crawled HTML pages: length, uppercase letters, "
              "underscores, spaces, double slashes, parameters, session parameters and path depth. One finding per "
              "rule with count.",
       logic="Session-ID in der URL: Warnung. Zu lang, Großbuchstaben, Leerzeichen, doppelter Schrägstrich, viele "
             "Parameter: Hinweis. Unterstrich oder große Tiefe: Info. ## Session ID in the URL: warning. Too long, "
             "uppercase, spaces, double slash, many parameters: note. Underscore or great depth: info.",
       fix="URLs klein schreiben, Wörter mit Bindestrich trennen, Sitzungen per Cookie statt per Parameter führen. "
           "## Write URLs in lowercase, separate words with hyphens and keep sessions in cookies instead of "
           "parameters.",
       refs=[GOOGLE + "crawling-indexing/url-structure"], profiles="sd")
def url_structure(snap):
    hits: dict[str, list[str]] = {key: [] for key, *_rest in _URL_RULES}
    for pg in snap.docs():
        parts = urlsplit(pg.url)
        path, query = parts.path, parse_qsl(parts.query, keep_blank_values=True)
        flags = {
            "session": any(k.lower() in _SESSION_PARAMS for k, _v in query),
            "params": len(query) > 3,
            "long": len(pg.url) > 115,
            "upper": any(c.isupper() for c in path),
            "space": " " in path or "%20" in path,
            "double": "//" in path,
            "underscore": "_" in path,
            "deep": len([s for s in path.split("/") if s]) > 5,
        }
        for key, hit in flags.items():
            if hit:
                hits[key].append(pg.url)
    out = []
    for key, severity, de, en in _URL_RULES:
        urls = hits[key]
        if urls:
            out.append(F("SEO-URL-001", severity, urls[0], f"{de} ({len(urls)} Seite(n))",
                         f"{en} ({len(urls)} page(s))", urls[0][:100]))
    return out


@check("SEO-CLK-001",
       title="Klicktiefe ## Click depth",
       why="Je mehr Klicks von der Startseite bis zu einer Seite nötig sind, desto seltener wird sie gecrawlt und "
           "desto weniger Gewicht bekommt sie. Wichtige Seiten sollten nach spätestens drei Klicks erreichbar "
           "sein. ## The more clicks it takes from the home page to a page, the less often it is crawled and the "
           "less weight it gets. Important pages should be reachable within three clicks.",
       method="Nutzt die Ebene jeder gecrawlten Seite (Startseite = Ebene 1, kürzester Weg über Links). Ab Ebene 5 "
              "sind mehr als drei Klicks nötig. Der Crawl endet bei Ebene 6. ## Uses the level of each crawled page "
              "(home page = level 1, shortest path via links). From level 5 more than three clicks are needed. The "
              "crawl ends at level 6.",
       logic="Seiten erst nach mehr als drei Klicks erreichbar: Hinweis. Crawl bis zur Grenze: Info. ## Pages "
             "reachable only after more than three clicks: note. Crawl reached the limit: info.",
       fix="Wichtige Seiten aus Menü, Startseite oder Kategorieseiten direkt verlinken und flachere Strukturen "
           "bauen. ## Link important pages directly from the menu, home page or category pages and build flatter "
           "structures.",
       refs=[GOOGLE + "crawling-indexing/links-crawlable"], profiles="sd")
def click_depth(snap):
    docs = snap.docs()
    out = []
    deep = [pg for pg in docs if pg.depth >= 5]
    if deep:
        out.append(F("SEO-CLK-001", S.NOTE, deep[0].url,
                     f"{len(deep)} Seite(n) erst nach mehr als 3 Klicks erreichbar",
                     f"{len(deep)} page(s) reachable only after more than 3 clicks",
                     f"max. {max(pg.depth for pg in deep) - 1} Klicks"))
    if any(pg.depth >= LIMITS.max_depth for pg in docs):
        out.append(F("SEO-CLK-001", S.INFO, snap.target.url,
                     f"Der Crawl endet bei Ebene {LIMITS.max_depth}: tiefer liegende Seiten wurden nicht erfasst",
                     f"The crawl ends at level {LIMITS.max_depth}: deeper pages were not covered"))
    return out


def _parse_robots(text: str) -> dict:
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    unknown: list[str] = []
    sitemaps: list[str] = []
    orphans = noindex = delay = 0
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    in_rules = False
    for raw in text.splitlines()[:5000]:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not sep:
            unknown.append(line[:60])
        elif key == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif key in ("allow", "disallow"):
            if not agents:
                orphans += 1
            else:
                rules.append((key, value))
                in_rules = True
        elif key == "sitemap":
            sitemaps.append(value)
        elif key == "crawl-delay":
            delay += 1
        elif key == "noindex":
            noindex += 1
        elif key not in ("host", "clean-param"):
            unknown.append(line[:60])
    if agents:
        groups.append((agents, rules))
    return {"groups": groups, "unknown": unknown, "sitemaps": sitemaps, "orphans": orphans,
            "noindex": noindex, "delay": delay}


def _blocks_assets(value: str) -> bool:
    low = value.strip().lower()
    return bool(_ASSET_RULE.search(low)) or low.rstrip("*/") in _ASSET_DIRS


@check("SEO-RBD-001",
       title="robots.txt im Detail ## robots.txt in detail",
       why="Eine robots.txt kann mehr kaputt machen als die Komplettsperre: gesperrte CSS- und JavaScript-Dateien "
           "verhindern, dass Google die Seite darstellen kann, Tippfehler werden ignoriert, und Regeln wirken nur "
           "innerhalb einer User-agent-Gruppe. ## A robots.txt can break more than the full block: blocked CSS and "
           "JavaScript files stop Google from rendering the page, typos are ignored and rules only work inside a "
           "user-agent group.",
       method="Liest die beim Crawl geholte robots.txt (höchstens 5.000 Zeilen) und prüft: Größe, unbekannte "
              "Anweisungen, Regeln ohne User-agent, gesperrte CSS/JS-Dateien und Ordner, Sperre von Googlebot oder "
              "Bingbot, Sitemap-Zeilen ohne https-Adresse, Crawl-delay und noindex. Die Komplettsperre für alle "
              "meldet SEO-ROB-001. ## Reads the robots.txt fetched during the crawl (at most 5,000 lines) and "
              "checks: size, unknown directives, rules without user-agent, blocked CSS/JS files and folders, block "
              "of Googlebot or Bingbot, sitemap lines without an https address, crawl-delay and noindex. The full "
              "block for all is reported by SEO-ROB-001.",
       logic="Googlebot oder Bingbot komplett gesperrt, über 500.000 Bytes oder CSS/JS gesperrt: Warnung. Unbekannte "
             "Anweisung, Regel ohne User-agent, noindex, Sitemap ohne https: Hinweis. Crawl-delay oder keine Datei: "
             "Info. ## Googlebot or Bingbot fully blocked, above 500,000 bytes or CSS/JS blocked: warning. Unknown "
             "directive, rule without user-agent, noindex, sitemap without https: note. Crawl-delay or no file: info.",
       fix="CSS und JavaScript freigeben, Tippfehler beheben, jede Regel unter ein User-agent stellen und Sitemaps "
           "mit vollständiger https-Adresse eintragen. ## Allow CSS and JavaScript, fix typos, put every rule under "
           "a user-agent and list sitemaps with a full https address.",
       refs=[GOOGLE + "crawling-indexing/robots/intro", "https://www.rfc-editor.org/rfc/rfc9309"], profiles="sd")
def robots_depth(snap):
    text, url = snap.robots_txt, snap.target.url
    if text is None:
        return [F("SEO-RBD-001", S.INFO, url, "Keine robots.txt gefunden oder sie war nicht abrufbar",
                  "No robots.txt found or it was not reachable")]
    parsed = _parse_robots(text)
    out = []
    if len(text.encode("utf-8", errors="ignore")) >= 500_000:
        out.append(F("SEO-RBD-001", S.WARNING, url, "Die robots.txt ist mindestens 500.000 Bytes groß (Google liest nur so viel)",
                     "The robots.txt is at least 500,000 bytes (Google reads only that much)"))
    blocked_assets, blocked_bots = [], []
    for agents, rules in parsed["groups"]:
        names = set(agents)
        relevant = "*" in names or bool(names & _KNOWN_AGENTS)
        for directive, value in rules:
            if directive != "disallow":
                continue
            if relevant and _blocks_assets(value):
                blocked_assets.append(value)
            if value == "/" and names & _KNOWN_AGENTS and "*" not in names:
                blocked_bots.append(", ".join(sorted(names & _KNOWN_AGENTS)))
    if blocked_assets:
        out.append(F("SEO-RBD-001", S.WARNING, url, f"{len(blocked_assets)} Regel(n) sperren CSS- oder JavaScript-Dateien",
                     f"{len(blocked_assets)} rule(s) block CSS or JavaScript files", blocked_assets[0][:60]))
    if blocked_bots:
        out.append(F("SEO-RBD-001", S.WARNING, url, "Googlebot oder Bingbot ist in der robots.txt komplett gesperrt",
                     "Googlebot or Bingbot is fully blocked in robots.txt", blocked_bots[0][:60]))
    if parsed["unknown"]:
        out.append(F("SEO-RBD-001", S.NOTE, url, f"{len(parsed['unknown'])} unbekannte Zeile(n) in der robots.txt (Tippfehler?)",
                     f"{len(parsed['unknown'])} unknown line(s) in robots.txt (typo?)", parsed["unknown"][0]))
    if parsed["orphans"]:
        out.append(F("SEO-RBD-001", S.NOTE, url, f"{parsed['orphans']} Regel(n) ohne vorheriges User-agent",
                     f"{parsed['orphans']} rule(s) without a preceding user-agent"))
    if parsed["noindex"]:
        out.append(F("SEO-RBD-001", S.NOTE, url, "noindex in der robots.txt wird von Google nicht mehr unterstützt",
                     "noindex in robots.txt is no longer supported by Google"))
    badmaps = [m for m in parsed["sitemaps"] if not m.lower().startswith("https:")]
    if badmaps:
        out.append(F("SEO-RBD-001", S.NOTE, url, f"{len(badmaps)} Sitemap-Zeile(n) ohne vollständige https-Adresse",
                     f"{len(badmaps)} sitemap line(s) without a full https address", badmaps[0][:80]))
    if parsed["delay"]:
        out.append(F("SEO-RBD-001", S.INFO, url, "Crawl-delay gesetzt (Google ignoriert ihn, Bing beachtet ihn)",
                     "Crawl-delay set (Google ignores it, Bing honours it)"))
    return out


@check("SEO-FAV-001",
       title="Favicon ## Favicon",
       why="Google zeigt das Favicon in den mobilen Suchergebnissen, und Browser zeigen es in Tabs und Lesezeichen. "
           "Fehlt es oder liefert die Adresse einen Fehler, wirkt die Website unfertig. ## Google shows the favicon "
           "in mobile search results, and browsers show it in tabs and bookmarks. If it is missing or the address "
           "returns an error, the website looks unfinished.",
       method="Sucht auf der Startseite link rel=icon (oder apple-touch-icon) und ruft die Adresse einmal ab. Ohne "
              "Link wird /favicon.ico abgerufen. Fremde Adressen und data:-Adressen werden nicht abgerufen. ## "
              "Looks on the home page for link rel=icon (or apple-touch-icon) and fetches the address once. Without "
              "a link /favicon.ico is fetched. Foreign addresses and data: addresses are not fetched.",
       logic="Deklariertes Favicon liefert Fehler oder HTML: Warnung. Kein Favicon: Hinweis. Nur /favicon.ico ohne "
             "Link: Info. ## Declared favicon returns an error or HTML: warning. No favicon: note. Only "
             "/favicon.ico without a link: info.",
       fix="Im head <link rel=\"icon\" href=\"/favicon.ico\"> (oder PNG/SVG) einbinden, mindestens 48 mal 48 Pixel. "
           "## Add <link rel=\"icon\" href=\"/favicon.ico\"> (or PNG/SVG) in the head, at least 48 by 48 pixels.",
       refs=[GOOGLE + "appearance/favicon-in-search"], profiles="sd", source="network")
def favicon(snap):
    data = snap.extra.get("passive")
    if data is None:
        raise CheckSkipped("no_passive_data")
    fav = data.get("favicon")
    if not isinstance(fav, dict) or fav.get("skipped"):
        raise CheckSkipped("no_html")
    url = snap.target.url
    if fav.get("inline") or fav.get("external"):
        return []
    fetched = fav.get("fetch")
    if not isinstance(fetched, dict) or fetched.get("error"):
        raise CheckSkipped("favicon_unreachable")
    status = fetched.get("status")
    ctype = str(fetched.get("content_type", ""))
    if fav.get("declared"):
        if status != 200:
            return [F("SEO-FAV-001", S.WARNING, url, f"Das im HTML deklarierte Favicon liefert HTTP {status}",
                      f"The favicon declared in the HTML returns HTTP {status}")]
        if "html" in ctype:
            return [F("SEO-FAV-001", S.WARNING, url, "Das deklarierte Favicon liefert HTML statt eines Bildes",
                      "The declared favicon returns HTML instead of an image")]
        return []
    if status == 200 and "html" not in ctype:
        return [F("SEO-FAV-001", S.INFO, url, "Kein Favicon-Link im HTML, nur /favicon.ico ist vorhanden",
                  "No favicon link in the HTML, only /favicon.ico exists")]
    return [F("SEO-FAV-001", S.NOTE, url, "Kein Favicon gefunden", "No favicon found")]
