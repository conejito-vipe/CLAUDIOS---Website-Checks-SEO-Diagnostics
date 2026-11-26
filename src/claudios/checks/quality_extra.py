"""Weitere Prüfungen zu Auslieferung, Barrierefreiheit, Datenschutz-Signalen und Sicherheit. Sie werten den Snapshot und
die Zusatzdaten aus core/probe_extra.py aus und lösen keine eigenen Anfragen aus."""
from __future__ import annotations

import re
import statistics
from urllib.parse import urljoin

from ..core.crawler import norm
from ..core.probe_extra import alt_host, external_hosts
from ..core.registry import check
from ._util import CheckSkipped, F, S
from .privacy import SERVICES
from .schema_more import _CART
from .seo_extra import _noindex

MDN = "https://developer.mozilla.org/en-US/docs/Web/"
WEBDEV = "https://web.dev/articles/"
WCAG = "https://www.w3.org/WAI/WCAG22/Understanding/"


def _extra(snap) -> dict:
    data = snap.extra.get("extra")
    if not isinstance(data, dict) or data.get("skipped"):
        raise CheckSkipped("no_extra_data")
    return data


def _first(snap):
    docs = snap.docs()
    if not docs:
        raise CheckSkipped("no_html")
    return docs[0]


def _css_texts(snap) -> list[str]:
    texts = [str(rec.get("text") or "") for rec in (snap.extra.get("assets") or {}).get("css", [])]
    for pg in snap.docs()[:5]:
        texts.extend(style.get_text() for style in pg.soup.find_all("style"))
    return texts


# ---------------------------------------------------------------- Adress-Varianten


@check("SEO-VAR-001",
       title="Adress-Varianten (http, www) ## Address variants (http, www)",
       why="Ist eine Website unter http und https oder mit und ohne www gleichzeitig erreichbar, entstehen doppelte "
           "Seiten für Suchmaschinen, und unverschlüsselte Aufrufe bleiben möglich. ## When a website is reachable "
           "under both http and https or with and without www, search engines see duplicate pages and unencrypted "
           "requests remain possible.",
       method="Je eine Anfrage ohne Weiterleitung an http://<Domain>/ und an die andere www-Schreibweise (https und "
              "http). Die http-Anfrage geht ohne Daten und nur an die eigene Domain. Nur Stammdomain und www-Variante "
              "werden verglichen. ## One request without following redirects each to http://<domain>/ and to the "
              "other www spelling (https and http). The http request carries no data and goes only to the own domain. "
              "Only the root domain and the www variant are compared.",
       logic="http liefert Inhalt statt Weiterleitung: Warnung. Andere Schreibweise liefert eigenen Inhalt statt "
             "Weiterleitung: Warnung. Weiterleitung mit 302/307 statt 301/308: Hinweis. ## http serves content "
             "instead of redirecting: warning. Other spelling serves its own content instead of redirecting: "
             "warning. Redirect with 302/307 instead of 301/308: note.",
       fix="Alle Varianten per 301 oder 308 auf die eine bevorzugte https-Adresse weiterleiten. ## Redirect all "
           "variants with 301 or 308 to the one preferred https address.",
       refs=[MDN + "HTTP/Redirections", "https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls"],
       profiles="sd", source="network")
def address_variants(snap):
    data = _extra(snap)["variants"]
    items = data.get("items") or {}
    if not any("status" in rec for rec in items.values()):
        raise CheckSkipped("variants_unreachable")
    url = snap.target.url
    out = []
    labels = {"http": ("http", "http"), "http_alt": (f"http://{data.get('alt')}", f"http://{data.get('alt')}"),
              "https_alt": (f"https://{data.get('alt')}", f"https://{data.get('alt')}")}
    for name, rec in items.items():
        if "error" in rec:
            continue
        de, en = labels[name]
        status, loc = rec["status"], rec["location"]
        if 300 <= status < 400 and loc:
            if status in (302, 303, 307):
                out.append(F("SEO-VAR-001", S.NOTE, url, f"{de} leitet nur vorläufig (HTTP {status}) weiter",
                             f"{en} redirects only temporarily (HTTP {status})", f"{name} -> {loc[:120]}"))
        elif status == 200:
            what = "mit eigenem Inhalt" if name != "http" else "ohne Weiterleitung auf https"
            what_en = "with its own content" if name != "http" else "without a redirect to https"
            out.append(F("SEO-VAR-001", S.WARNING, url, f"{de} antwortet {what} (HTTP 200)",
                         f"{en} answers {what_en} (HTTP 200)", name))
    return out


# ---------------------------------------------------------------- Barrierefreiheitserklärung

_ACCESS = re.compile(r"barrierefreiheit|barrierefrei|accessibility[\s-]*statement|accessibility", re.I)


@check("PRV-BFS-001",
       title="Barrierefreiheitserklärung verlinkt ## Accessibility statement linked",
       why="Für bestimmte Angebote (zum Beispiel Online-Shops und Dienstleistungen für Verbraucher) schreibt das "
           "Barrierefreiheitsstärkungsgesetz seit dem 28. Juni 2025 eine Barrierefreiheitserklärung vor. Auch ohne "
           "Pflicht hilft sie Menschen mit Einschränkungen. ## For certain offers (for example online shops and "
           "services for consumers) the German accessibility act has required an accessibility statement since "
           "28 June 2025. Even without an obligation it helps people with disabilities.",
       method="Sucht in den Links der gecrawlten Seiten nach Barrierefreiheit oder Accessibility im Linktext oder in "
              "der Adresse und erkennt Shops an Warenkorb- und Kasse-Elementen. Ob eine Pflicht besteht, kann das "
              "Programm nicht entscheiden (Ausnahmen gelten zum Beispiel für Kleinstunternehmen mit "
              "Dienstleistungen); das ist keine Rechtsberatung. ## Looks in the links of the crawled pages for "
              "accessibility in the link text or address and recognises shops by cart and checkout elements. "
              "Whether an obligation exists cannot be decided by the program (exceptions apply, for example, to "
              "micro-enterprises offering services); this is not legal advice.",
       logic="Kein Link bei einem erkannten Shop: Hinweis. Sonst kein Link: Info. ## No link on a recognised shop: "
             "note. Otherwise no link: info.",
       fix="Eine Seite 'Barrierefreiheitserklärung' erstellen (Stand der Konformität, Feedback-Kontakt, "
           "Schlichtungsstelle) und im Footer verlinken. ## Create an 'accessibility statement' page (conformance "
           "status, feedback contact, enforcement body) and link it in the footer.",
       refs=["https://www.gesetze-im-internet.de/bfsg/", "https://www.w3.org/WAI/planning/statements/"],
       profiles="qsd")
def accessibility_statement(snap):
    docs = snap.docs()
    if not docs:
        raise CheckSkipped("no_html")
    shop = False
    for pg in docs:
        for a in pg.soup.find_all("a", href=True):
            if _ACCESS.search(a.get_text(" ", strip=True)) or _ACCESS.search(str(a["href"])):
                return []
        if not shop:
            shop = any(_CART.search(el.get_text(" ", strip=True) or str(el.get("value") or ""))
                       for el in pg.soup.find_all(["button", "a", "input"]))
    return [F("PRV-BFS-001", S.NOTE if shop else S.INFO, docs[0].url,
              "Keine Barrierefreiheitserklärung verlinkt" + (" (Shop erkannt)" if shop else ""),
              "No accessibility statement linked" + (" (shop recognised)" if shop else ""))]


# ---------------------------------------------------------------- Global Privacy Control


def _tracking(hosts) -> list[str]:
    out = []
    for host in hosts:
        for suffix, name, category in SERVICES:
            if category == "tracking" and (host == suffix or host.endswith("." + suffix)) and name not in out:
                out.append(name)
    return out


@check("PRV-GPC-001",
       title="Global Privacy Control (GPC) ## Global Privacy Control (GPC)",
       why="GPC ist ein Signal des Browsers, das Tracking und Weitergabe von Daten ablehnt. In einigen Rechtsräumen "
           "(zum Beispiel Kalifornien) ist es verbindlich. Eine Website kann es auswerten und das über "
           "/.well-known/gpc.json erklären. ## GPC is a browser signal that declines tracking and the sale of data. "
           "In some jurisdictions (for example California) it is binding. A website can honour it and declare this "
           "in /.well-known/gpc.json.",
       method="Lädt die Startseite einmal zusätzlich mit dem Header Sec-GPC: 1, vergleicht die eingebundenen "
              "Tracking-Dienste mit der Seite ohne Signal und ruft /.well-known/gpc.json ab. Eine Auswertung allein "
              "im Browser (navigator.globalPrivacyControl) wird im Quelltext gesucht. ## Loads the home page once "
              "more with the header Sec-GPC: 1, compares the embedded tracking services with the page without the "
              "signal and fetches /.well-known/gpc.json. Handling in the browser only "
              "(navigator.globalPrivacyControl) is searched for in the source.",
       logic="Tracking-Dienste bleiben trotz Signal eingebunden und es gibt weder gpc.json noch Auswertung im Skript: "
             "Hinweis. Sonst nichts. In der EU ist GPC kein Ersatz für die Einwilligung. ## Tracking services stay "
             "embedded despite the signal and there is neither gpc.json nor handling in the script: note. "
             "Otherwise nothing. In the EU GPC is no substitute for consent.",
       fix="Das Signal serverseitig oder im Skript auswerten (Tracking dann nicht laden) und /.well-known/gpc.json "
           "mit {\"gpc\": true} veröffentlichen. ## Honour the signal on the server or in script (do not load "
           "tracking then) and publish /.well-known/gpc.json with {\"gpc\": true}.",
       refs=["https://globalprivacycontrol.org/", "https://privacycg.github.io/gpc-spec/"],
       profiles="sd", source="network")
def global_privacy_control(snap):
    data = _extra(snap)["gpc"]
    signalled = data.get("hosts_with_signal")
    if signalled is None:
        raise CheckSkipped("gpc_unreachable")
    first = _first(snap)
    plain = external_hosts(first.html, first.url, snap.target.host, snap.target.registrable)
    still = _tracking(set(plain) & set(signalled))
    if not still or data.get("declared"):
        return []
    sources = first.html + "".join(str(r.get("text") or "") for r in (snap.extra.get("assets") or {}).get("js", []))
    if "globalprivacycontrol" in sources.lower():
        return []
    return [F("PRV-GPC-001", S.NOTE, first.url,
              f"Mit dem GPC-Signal bleiben Tracking-Dienste eingebunden: {', '.join(still[:4])}",
              f"With the GPC signal tracking services stay embedded: {', '.join(still[:4])}", ", ".join(still))]


# ---------------------------------------------------------------- Sitemap-Abgleich


@check("SEO-SMX-001",
       title="Sitemap im Abgleich mit dem Crawl ## Sitemap compared with the crawl",
       why="Eine Sitemap soll nur indexierbare Seiten nennen. Steht dort eine Seite mit noindex oder mit einer "
           "anderen Canonical-URL, sendet die Website Suchmaschinen widersprüchliche Signale. Wichtige Seiten, die "
           "fehlen, werden später gefunden. ## A sitemap should list only indexable pages. If it lists a page with "
           "noindex or a different canonical URL the website sends search engines contradictory signals. Important "
           "pages that are missing are found later.",
       method="Vergleicht die Adressen der Sitemap mit den gecrawlten Seiten: noindex, abweichende Canonical-URL "
              "und Seiten, die der Crawl gefunden hat, die aber in der Sitemap fehlen (nur bei vollständig gelesener "
              "Sitemap). Es gibt keine eigenen Anfragen. ## Compares the sitemap addresses with the crawled pages: "
              "noindex, differing canonical URL and pages the crawl found that are missing from the sitemap (only "
              "when the sitemap was read completely). No requests of its own.",
       logic="noindex oder fremde Canonical in der Sitemap: Warnung. Mehr als jede fünfte gecrawlte Seite fehlt in der "
             "Sitemap: Hinweis. ## noindex or foreign canonical in the sitemap: warning. More than one in five "
             "crawled pages missing from the sitemap: note.",
       fix="Nur indexierbare Seiten mit ihrer Canonical-URL in die Sitemap aufnehmen und neue Seiten automatisch "
           "ergänzen. ## List only indexable pages with their canonical URL in the sitemap and add new pages "
           "automatically.",
       refs=["https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap"],
       profiles="sd", source="network")
def sitemap_vs_crawl(snap):
    sm = snap.extra.get("sitemap")
    if not isinstance(sm, dict) or not sm.get("found"):
        raise CheckSkipped("no_sitemap")
    listed = {norm(u) for u in sm.get("urls") or []}
    out = []
    for pg in snap.docs():
        key = norm(pg.url)
        if key not in listed:
            continue
        if _noindex(pg):
            out.append(F("SEO-SMX-001", S.WARNING, pg.url, "Seite steht in der Sitemap, ist aber auf noindex gesetzt",
                         "Page is in the sitemap but set to noindex", pg.url[:160]))
            continue
        link = pg.soup.find("link", rel=lambda v: v and "canonical" in [str(x).lower() for x in (v if isinstance(v, list) else [v])])
        href = str(link.get("href", "")).strip() if link else ""
        if href and norm(urljoin(pg.url, href)) != key:
            out.append(F("SEO-SMX-001", S.WARNING, pg.url, "Seite steht in der Sitemap, ihre Canonical-URL ist eine andere",
                         "Page is in the sitemap but its canonical URL is a different one", href[:160]))
    if sm.get("total") and not sm.get("truncated") and not sm.get("index"):
        pages = [pg for pg in snap.docs() if pg.status == 200 and not _noindex(pg)]
        missing = [pg for pg in pages if norm(pg.url) not in listed]
        if len(pages) >= 5 and len(missing) * 5 > len(pages):
            out.append(F("SEO-SMX-001", S.NOTE, missing[0].url,
                         f"{len(missing)} von {len(pages)} gecrawlten Seiten fehlen in der Sitemap",
                         f"{len(missing)} of {len(pages)} crawled pages are missing from the sitemap",
                         missing[0].url[:160]))
    return out


# ---------------------------------------------------------------- Bilder


@check("HTM-IMG-002",
       title="Bilder: Größe, Format und Layout ## Images: size, format and layout",
       why="Große Bilder sind meist der größte Teil einer Seite. Fehlen Breite und Höhe, springt das Layout beim Laden "
           "(Cumulative Layout Shift), und Bilder weit unten sollten erst beim Scrollen geladen werden. ## Large "
           "images are usually the biggest part of a page. Without width and height the layout jumps while loading "
           "(cumulative layout shift), and images far down should load only when scrolled to.",
       method="Wertet die img-Elemente des HTML aus (width und height, loading=lazy ab dem vierten Bild) und fragt "
              "bis zu acht Bilder der eigenen Domain mit HEAD ab (Typ und Größe). ## Evaluates the img elements of "
              "the HTML (width and height, loading=lazy from the fourth image) and queries up to eight images of the "
              "own domain with HEAD (type and size).",
       logic="Bild über 1 MB: Warnung. Über 300 KB oder JPEG/PNG über 150 KB: Hinweis. Fehlende Maße bei mindestens "
             "der Hälfte der Bilder: Hinweis. Kein lazy-loading bei vielen Bildern: Info. ## Image above 1 MB: "
             "warning. Above 300 KB or JPEG/PNG above 150 KB: note. Missing dimensions on at least half of the "
             "images: note. No lazy loading with many images: info.",
       fix="Bilder verkleinern und als WebP oder AVIF ausliefern, width und height setzen, loading=\"lazy\" für Bilder "
           "unterhalb des sichtbaren Bereichs. ## Shrink images and serve them as WebP or AVIF, set width and "
           "height, use loading=\"lazy\" for images below the fold.",
       refs=[WEBDEV + "optimize-cls", WEBDEV + "browser-level-image-lazy-loading"], profiles="sd", source="network")
def images(snap):
    data = _extra(snap)
    out = []
    first = _first(snap)
    imgs = first.soup.find_all("img")
    if len(imgs) >= 2:
        nodim = [i for i in imgs if not (i.get("width") and i.get("height"))]
        if len(nodim) * 2 >= len(imgs):
            out.append(F("HTM-IMG-002", S.NOTE, first.url, f"{len(nodim)} von {len(imgs)} Bildern ohne width und height",
                         f"{len(nodim)} of {len(imgs)} images without width and height"))
    if len(imgs) > 6 and not any(str(i.get("loading", "")).lower() == "lazy" for i in imgs[3:]):
        out.append(F("HTM-IMG-002", S.INFO, first.url, f"Kein Bild von {len(imgs)} lädt verzögert (loading=lazy)",
                     f"None of {len(imgs)} images loads lazily (loading=lazy)"))
    for rec in data["images"]:
        size = rec.get("length")
        if rec.get("status") != 200 or not size:
            continue
        kind = rec.get("type", "")
        legacy = "jpeg" in kind or "png" in kind
        if size > 1_000_000:
            sev = S.WARNING
        elif size > 300_000 or (legacy and size > 150_000):
            sev = S.NOTE
        else:
            continue
        kb = size // 1000
        out.append(F("HTM-IMG-002", sev, rec["url"], f"Bild mit {kb} KB ({kind or 'unbekannter Typ'})",
                     f"Image with {kb} KB ({kind or 'unknown type'})", rec["url"][:160]))
    return out


# ---------------------------------------------------------------- Caching und Kompression statischer Dateien


@check("SEO-ACH-001",
       title="Caching und Kompression von CSS und JavaScript ## Caching and compression of CSS and JavaScript",
       why="Statische Dateien ändern sich selten. Mit langem Cache lädt der Browser sie nur einmal, und mit Kompression "
           "sind sie deutlich kleiner. Beides spart Ladezeit und Datenvolumen. ## Static files rarely change. With "
           "a long cache the browser loads them once, and with compression they are much smaller. Both save "
           "loading time and data.",
       method="Fragt die bereits geladenen CSS- und JS-Dateien (bis zu je sechs) mit HEAD ab und wertet "
              "Cache-Control, Expires und Content-Encoding aus. ## Queries the already loaded CSS and JS files (up "
              "to six each) with HEAD and evaluates Cache-Control, Expires and Content-Encoding.",
       logic="Kein Cache-Header oder no-store bei den meisten Dateien: Hinweis. max-age unter einem Tag: Info. "
             "Dateien über 1.500 Bytes ohne Kompression: Hinweis. ## No cache header or no-store on most files: "
             "note. max-age below one day: info. Files above 1,500 bytes without compression: note.",
       fix="Für CSS und JS Cache-Control: public, max-age=31536000, immutable mit Versions- oder Hash-Dateinamen "
           "setzen und gzip oder Brotli aktivieren. ## Set Cache-Control: public, max-age=31536000, immutable with "
           "versioned or hashed file names for CSS and JS and enable gzip or Brotli.",
       refs=[MDN + "HTTP/Caching", WEBDEV + "http-cache"], profiles="sd", source="network")
def asset_headers(snap):
    files = [r for r in _extra(snap)["assets"] if r["status"] == 200]
    if not files:
        raise CheckSkipped("no_assets")
    out = []
    uncached = [r for r in files if not r["cache"] and not r["expires"] and not r["etag"] or "no-store" in r["cache"]]
    if len(uncached) * 2 > len(files):
        out.append(F("SEO-ACH-001", S.NOTE, uncached[0]["url"],
                     f"{len(uncached)} von {len(files)} CSS- und JS-Dateien ohne Cache-Angabe",
                     f"{len(uncached)} of {len(files)} CSS and JS files without cache information", uncached[0]["url"][:160]))
    short = []
    for rec in files:
        match = re.search(r"max-age=(\d+)", rec["cache"])
        if match and int(match.group(1)) < 86400 and "immutable" not in rec["cache"]:
            short.append(rec)
    if short and len(short) * 2 > len(files):
        out.append(F("SEO-ACH-001", S.INFO, short[0]["url"],
                     f"{len(short)} Dateien mit einer Cache-Zeit unter einem Tag",
                     f"{len(short)} files with a cache time below one day", short[0]["url"][:160]))
    plain = [r for r in files if (r["length"] or 0) > 1500 and not any(e in r["encoding"] for e in ("gzip", "br", "zstd", "deflate"))]
    if plain:
        out.append(F("SEO-ACH-001", S.NOTE, plain[0]["url"], f"{len(plain)} CSS- oder JS-Dateien ohne Komprimierung",
                     f"{len(plain)} CSS or JS files without compression", plain[0]["url"][:160]))
    return out


# ---------------------------------------------------------------- Fremd-Domains (Lieferkette)


@check("SEC-SUP-001",
       title="Ablauf der Domains eingebundener Fremdskripte ## Expiry of the domains of embedded third-party scripts",
       why="Läuft die Domain eines eingebundenen Skripts ab, kann jemand sie übernehmen und Schadcode an alle Besucher "
           "ausliefern (Lieferkettenangriff). ## When the domain of an embedded script expires somebody can take it "
           "over and serve malicious code to all visitors (supply chain attack).",
       method="Nur mit eingeschaltetem Schalter 'rdap' auf der Seite Externe Dienste. Fragt bis zu fünf Domains "
              "fremder Skripte per RDAP ab (nur Domainnamen werden gesendet, der Server sieht die IP-Adresse des "
              "Nutzers). ## Only with the switch 'rdap' on the External services page turned on. Queries up to five "
              "domains of third-party scripts via RDAP (only domain names are sent, the server sees the user's IP "
              "address).",
       logic="Abgelaufen oder unter 14 Tagen oder pending delete: Fehler. Unter 60 Tagen: Hinweis. Kein Skript "
             "fremder Domains: nichts. ## Expired or below 14 days or pending delete: error. Below 60 days: note. "
             "No script of foreign domains: nothing.",
       fix="Das Skript selbst hosten oder entfernen und den Anbieter informieren. ## Host the script yourself or "
           "remove it and inform the provider.",
       refs=["https://owasp.org/www-project-top-ten/2017/A9_2017-Using_Components_with_Known_Vulnerabilities",
             "https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.html"],
       profiles="sd", source="network")
def foreign_script_domains(snap):
    data = _extra(snap)["foreign_domains"]
    if data is None:
        raise CheckSkipped("rdap_disabled")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    from datetime import UTC, datetime

    out = []
    for rec in data["checked"]:
        if not rec.get("expires"):
            continue
        try:
            when = datetime.fromisoformat(rec["expires"])
        except ValueError:
            continue
        days = (when - datetime.now(UTC)).days
        danger = {"pendingdelete", "redemptionperiod"} & set(rec.get("statuses") or [])
        if days < 14 or danger:
            sev, de, en = S.ERROR, "läuft ab oder ist abgelaufen", "expires or has expired"
        elif days < 60:
            sev, de, en = S.NOTE, f"läuft in {days} Tagen ab", f"expires in {days} days"
        else:
            continue
        out.append(F("SEC-SUP-001", sev, snap.target.url, f"Die Domain {rec['domain']} eines eingebundenen Skripts {de}",
                     f"The domain {rec['domain']} of an embedded script {en}", rec["domain"]))
    return out


# ---------------------------------------------------------------- HTTP-Version und Antwortzeit


@check("SEO-HTV-001",
       title="HTTP-Protokoll und Antwortzeit ## HTTP protocol and response time",
       why="HTTP/2 lädt viele Dateien parallel über eine Verbindung und ist bei vielen kleinen Dateien deutlich "
           "schneller als HTTP/1.1. Eine langsame Antwort verzögert alles, was danach kommt. ## HTTP/2 loads many "
           "files in parallel over one connection and is much faster than HTTP/1.1 with many small files. A slow "
           "response delays everything that follows.",
       method="Liest aus dem einen TLS-Handshake, welches Protokoll der Server wählt (ALPN), und wertet die mittlere "
              "Antwortzeit der gecrawlten HTML-Seiten aus. Die Zeit ist eine Messung vom Standort des Programms aus "
              "und kein Laborwert. ## Reads from the single TLS handshake which protocol the server selects (ALPN) "
              "and evaluates the median response time of the crawled HTML pages. The time is measured from the "
              "program's location and not a lab value.",
       logic="Nur HTTP/1.1: Hinweis. Mittlere Antwortzeit über 1,5 Sekunden: Hinweis, über 3 Sekunden: Warnung. ## "
             "HTTP/1.1 only: note. Median response time above 1.5 seconds: note, above 3 seconds: warning.",
       fix="HTTP/2 (und möglichst HTTP/3) im Webserver oder beim Hoster aktivieren; langsame Antworten über "
           "Server-Cache, schnelleres Hosting oder weniger Datenbankabfragen verbessern. ## Enable HTTP/2 (and "
           "ideally HTTP/3) in the web server or at the host; improve slow responses with server caching, faster "
           "hosting or fewer database queries.",
       refs=[MDN + "HTTP/Guides/Evolution_of_HTTP", WEBDEV + "ttfb"], profiles="sd", source="network")
def http_version(snap):
    tls = snap.extra.get("tls")
    docs = [pg for pg in snap.docs() if pg.elapsed_ms]
    if not isinstance(tls, dict) and not docs:
        raise CheckSkipped("no_tls_data")
    url = snap.target.url
    out = []
    if isinstance(tls, dict) and not tls.get("error") and "alpn" in tls and tls["alpn"] != "h2":
        out.append(F("SEO-HTV-001", S.NOTE, url, "Der Server bietet nur HTTP/1.1 an (kein HTTP/2)",
                     "The server offers only HTTP/1.1 (no HTTP/2)", tls["alpn"] or "http/1.1"))
    if len(docs) >= 2:
        median = statistics.median(pg.elapsed_ms for pg in docs)
        if median > 1500:
            out.append(F("SEO-HTV-001", S.WARNING if median > 3000 else S.NOTE, url,
                         f"Die mittlere Antwortzeit beträgt {int(median)} ms", f"The median response time is {int(median)} ms",
                         f"{int(median)} ms"))
    return out


# ---------------------------------------------------------------- TLS-Ergänzungen


def _covers(names: list[str], host: str) -> bool:
    for name in names:
        if name == host or (name.startswith("*.") and host.split(".", 1)[-1] == name[2:] and host.count(".") == name.count(".")):
            return True
    return False


@check("TLS-EXT-001",
       title="HSTS-Preload und Zertifikatsnamen ## HSTS preload and certificate names",
       why="Mit HSTS-Preload ist die Website schon beim ersten Besuch nur per HTTPS erreichbar. Das Zertifikat muss "
           "außerdem alle Schreibweisen der Domain (mit und ohne www) abdecken, sonst erscheinen Warnungen. ## With "
           "HSTS preload the website is reachable only over HTTPS even on the first visit. The certificate must also "
           "cover every spelling of the domain (with and without www), otherwise warnings appear.",
       method="Wertet den HSTS-Header der Startseite aus (Voraussetzungen der Preload-Liste: max-age mindestens ein "
              "Jahr, includeSubDomains, preload) und prüft, ob die Zertifikatsnamen aus dem TLS-Handshake auch die "
              "andere www-Schreibweise abdecken. Certificate Transparency und OCSP-Stapling prüft das Programm nicht. "
              "## Evaluates the HSTS header of the home page (requirements of the preload list: max-age of at least "
              "one year, includeSubDomains, preload) and checks whether the certificate names from the TLS "
              "handshake also cover the other www spelling. The program does not check certificate transparency or "
              "OCSP stapling.",
       logic="HSTS erfüllt die Voraussetzungen, aber ohne preload: Info. Zertifikat deckt die andere "
             "www-Schreibweise nicht ab: Hinweis. ## HSTS meets the requirements but without preload: info. "
             "Certificate does not cover the other www spelling: note.",
       fix="HSTS mit max-age=31536000; includeSubDomains; preload senden und die Domain bei hstspreload.org anmelden "
           "(vorher prüfen, dass alle Unterdomains HTTPS können). Zertifikat um die fehlende Schreibweise "
           "erweitern. ## Send HSTS with max-age=31536000; includeSubDomains; preload and submit the domain at "
           "hstspreload.org (first make sure all subdomains support HTTPS). Extend the certificate with the missing "
           "spelling.",
       refs=["https://hstspreload.org/", MDN + "HTTP/Headers/Strict-Transport-Security"], profiles="sd", source="network")
def tls_extras(snap):
    tls = snap.extra.get("tls")
    if not isinstance(tls, dict) or tls.get("error"):
        raise CheckSkipped("no_tls_data")
    first = _first(snap)
    out = []
    hsts = first.headers.get("strict-transport-security", "").lower()
    match = re.search(r"max-age=(\d+)", hsts)
    if match and int(match.group(1)) >= 31536000 and "includesubdomains" in hsts and "preload" not in hsts:
        out.append(F("TLS-EXT-001", S.INFO, first.url, "HSTS erfüllt die Preload-Voraussetzungen, preload fehlt",
                     "HSTS meets the preload requirements, preload is missing", hsts[:120]))
    other = alt_host(snap.target.host, snap.target.registrable)
    names = tls.get("san") or []
    if other and names and not _covers(names, other):
        out.append(F("TLS-EXT-001", S.NOTE, first.url, f"Das Zertifikat deckt {other} nicht ab",
                     f"The certificate does not cover {other}", ", ".join(names[:5])))
    return out


# ---------------------------------------------------------------- Tastatur und Bewegung

_FOCUS_RULE = re.compile(r"([^{}]*:focus(?!-visible)[^{}]*)\{([^}]*)\}", re.I)
_OUTLINE_OFF = re.compile(r"outline\s*:\s*(none|0)\b", re.I)
_REPLACEMENT = re.compile(r"box-shadow|border|background|text-decoration|outline\s*:\s*[^;]*(solid|dotted|dashed|auto)", re.I)


@check("HTM-KEY-001",
       title="Tastaturbedienung und Bewegung ## Keyboard operation and motion",
       why="Wer ohne Maus arbeitet, braucht einen sichtbaren Fokus und einen Sprunglink zum Inhalt. Animationen "
           "sollten sich abschalten lassen, wenn Nutzer weniger Bewegung wünschen. ## Those who work without a mouse "
           "need a visible focus and a skip link to the content. Animations should be switchable when users prefer "
           "less motion.",
       method="Sucht im HTML der Startseite einen Sprunglink am Anfang, in den gelesenen CSS-Dateien Regeln, die den "
              "Fokusrahmen ohne Ersatz abschalten, und prüft, ob Animationen prefers-reduced-motion beachten. Eine "
              "Messung im Browser findet nicht statt, das Ergebnis ist ein Indiz. ## Looks in the HTML of the home "
              "page for a skip link at the start, in the CSS files read for rules that remove the focus outline "
              "without a replacement and checks whether animations respect prefers-reduced-motion. No browser "
              "measurement takes place, so the result is an indication.",
       logic="Fokusrahmen ohne Ersatz entfernt: Warnung. Navigation ohne Sprunglink: Hinweis. Animationen ohne "
             "prefers-reduced-motion: Info. ## Focus outline removed without a replacement: warning. Navigation "
             "without a skip link: note. Animations without prefers-reduced-motion: info.",
       fix="Fokus mit :focus-visible gestalten statt ihn zu entfernen, einen Link 'Zum Inhalt springen' als erstes "
           "Element einbauen und Animationen in @media (prefers-reduced-motion: reduce) abschwächen. ## Style the "
           "focus with :focus-visible instead of removing it, add a 'skip to content' link as the first element and "
           "tone down animations in @media (prefers-reduced-motion: reduce).",
       refs=[WCAG + "focus-visible", WCAG + "bypass-blocks", WCAG + "animation-from-interactions"])
def keyboard_and_motion(snap):
    first = _first(snap)
    css = "\n".join(_css_texts(snap))
    out = []
    focus_removed = [m.group(1).strip()[:60] for m in _FOCUS_RULE.finditer(css)
                     if _OUTLINE_OFF.search(m.group(2)) and not _REPLACEMENT.search(m.group(2))]
    if focus_removed and ":focus-visible" not in css.lower():
        out.append(F("HTM-KEY-001", S.WARNING, first.url, "Der Fokusrahmen wird ohne Ersatz entfernt",
                     "The focus outline is removed without a replacement", focus_removed[0]))
    body = first.soup.body
    if body is not None and body.find("nav") is not None:
        early = body.find_all("a", href=True, limit=6)
        skip = any(str(a["href"]).startswith("#") and len(str(a["href"])) > 1 and first.soup.find(id=str(a["href"])[1:])
                   for a in early)
        if not skip:
            out.append(F("HTM-KEY-001", S.NOTE, first.url, "Kein Sprunglink zum Hauptinhalt am Seitenanfang",
                         "No skip link to the main content at the top of the page"))
    low = css.lower()
    if ("@keyframes" in low or re.search(r"animation\s*:", low)) and "prefers-reduced-motion" not in low:
        out.append(F("HTM-KEY-001", S.INFO, first.url, "Animationen ohne Rücksicht auf prefers-reduced-motion",
                     "Animations without regard to prefers-reduced-motion"))
    return out


# ---------------------------------------------------------------- CMS-Zusatzpfade (aktiv)

CMS_KINDS = {
    "xmlrpc": (S.NOTE, "Die XML-RPC-Schnittstelle von WordPress ist erreichbar",
               "The WordPress XML-RPC interface is reachable"),
    "users": (S.WARNING, "Die Benutzerliste von WordPress ist öffentlich abrufbar",
              "The WordPress user list is publicly retrievable"),
    "admin": (S.INFO, "Die Joomla-Anmeldeseite ist öffentlich erreichbar", "The Joomla login page is publicly reachable"),
    "version": (S.NOTE, "Die Joomla-Versionsdatei ist öffentlich abrufbar", "The Joomla version file is publicly retrievable"),
}


@check("SEC-CMX-001",
       title="CMS-Zusatzpfade (WordPress, Joomla) ## CMS extra paths (WordPress, Joomla)",
       why="Offene Schnittstellen und Benutzerlisten helfen Angreifern beim Erraten von Zugängen und bei Angriffen auf "
           "bekannte Versionen. ## Open interfaces and user lists help attackers guess accounts and attack known "
           "versions.",
       method="Aktive Prüfung (Stufe 2, nur nach Verifizierung), nur wenn ein CMS erkannt wurde: je zwei feste Pfade "
              "per GET (WordPress: xmlrpc.php, wp-json/wp/v2/users; Joomla: administrator/, "
              "administrator/manifests/files/joomla.xml), nur HTTPS, keine Weiterleitungen, keine Anmeldung, kein "
              "Raten. Inhalte werden nicht gespeichert. ## Active check (level 2, only after verification), only "
              "when a CMS was recognised: two fixed paths each via GET (WordPress: xmlrpc.php, "
              "wp-json/wp/v2/users; Joomla: administrator/, administrator/manifests/files/joomla.xml), HTTPS only, "
              "no redirects, no login, no guessing. Content is not stored.",
       logic="Benutzerliste öffentlich: Warnung. XML-RPC oder Joomla-Versionsdatei: Hinweis. Joomla-Anmeldeseite: "
             "Info. Kein CMS erkannt oder Pfade nicht erreichbar: nicht ausgeführt. ## User list public: warning. "
             "XML-RPC or Joomla version file: note. Joomla login page: info. No CMS recognised or paths "
             "unreachable: not executed.",
       fix="XML-RPC und die Benutzer-Schnittstelle sperren (Plugin oder Serverregel), Joomla-Versionsdatei und "
           "administrator/ per IP oder zusätzlichem Passwortschutz einschränken. ## Block XML-RPC and the user "
           "endpoint (plugin or server rule), restrict the Joomla version file and administrator/ by IP or "
           "additional password protection.",
       refs=["https://owasp.org/www-project-web-security-testing-guide/",
             "https://developer.wordpress.org/rest-api/reference/users/"],
       profiles="sd", kind="active", source="network")
def cms_paths(snap):
    data = snap.extra.get("cms")
    if data is None:
        raise CheckSkipped("no_cms_or_level")
    if data["total"] and data["errors"] >= data["total"]:
        raise CheckSkipped("paths_unreachable")
    first = _first(snap)
    out = []
    for rec in data["hits"]:
        sev, de, en = CMS_KINDS[rec["kind"]]
        out.append(F("SEC-CMX-001", sev, first.url.rstrip("/") + "/" + rec["path"], de, en, rec["path"]))
    return out


# ---------------------------------------------------------------- Seitengewicht

@check("SEO-WGT-001",
       title="Seitengewicht und blockierende Skripte ## Page weight and blocking scripts",
       why="Große HTML-Seiten, viele Skripte und viele Fremdserver verlangsamen den Aufbau der Seite, besonders auf "
           "dem Handy. Skripte im Kopf ohne async oder defer blockieren die Darstellung. ## Large HTML pages, many "
           "scripts and many third-party servers slow down page rendering, especially on phones. Scripts in the "
           "head without async or defer block rendering.",
       method="Wertet je HTML-Seite die Größe des Dokuments, die Zahl der Skripte, Stile und Bilder, die Zahl "
              "fremder Server und blockierende Skripte im head aus. Es gibt keine eigenen Anfragen; Bilder und "
              "Skripte selbst werden hier nicht gewogen. ## Evaluates per HTML page the size of the document, the "
              "number of scripts, styles and images, the number of third-party servers and blocking scripts in the "
              "head. No requests of its own; images and scripts themselves are not weighed here.",
       logic="HTML über 1 MB: Warnung, über 500 KB: Hinweis. Über 30 Skripte, über 10 Fremdserver oder mehr als 3 "
             "blockierende Skripte: Hinweis. ## HTML above 1 MB: warning, above 500 KB: note. More than 30 scripts, "
             "more than 10 third-party servers or more than 3 blocking scripts: note.",
       fix="Inhalte aufteilen, Skripte bündeln und mit defer laden, nicht benötigte Fremdserver entfernen. ## Split "
           "content, bundle scripts and load them with defer, remove third-party servers that are not needed.",
       refs=[WEBDEV + "render-blocking-resources", WEBDEV + "optimize-long-tasks"])
def page_weight(snap):
    out = []
    for pg in snap.docs()[:25]:
        if pg.size > 1_000_000:
            out.append(F("SEO-WGT-001", S.WARNING, pg.url, f"HTML-Dokument mit {pg.size // 1000} KB",
                         f"HTML document with {pg.size // 1000} KB", f"{pg.size} Bytes"))
        elif pg.size > 500_000:
            out.append(F("SEO-WGT-001", S.NOTE, pg.url, f"HTML-Dokument mit {pg.size // 1000} KB",
                         f"HTML document with {pg.size // 1000} KB", f"{pg.size} Bytes"))
    first = _first(snap)
    soup = first.soup
    scripts = soup.find_all("script", src=True)
    if len(scripts) > 30:
        out.append(F("SEO-WGT-001", S.NOTE, first.url, f"{len(scripts)} Skripte auf der Startseite",
                     f"{len(scripts)} scripts on the home page"))
    hosts = external_hosts(first.html, first.url, snap.target.host, snap.target.registrable)
    if len(hosts) > 10:
        out.append(F("SEO-WGT-001", S.NOTE, first.url, f"{len(hosts)} fremde Server auf der Startseite",
                     f"{len(hosts)} third-party servers on the home page", ", ".join(hosts[:6])))
    head = soup.head
    blocking = [s for s in (head.find_all("script", src=True) if head else [])
                if not s.has_attr("async") and not s.has_attr("defer") and str(s.get("type", "")).lower() != "module"]
    if len(blocking) > 3:
        out.append(F("SEO-WGT-001", S.NOTE, first.url, f"{len(blocking)} blockierende Skripte im head",
                     f"{len(blocking)} blocking scripts in the head", str(blocking[0].get("src", ""))[:120]))
    return out


# ---------------------------------------------------------------- BIMI und DANE


def _dns_records(snap, key: str):
    data = snap.extra.get("dns")
    if data is None:
        raise CheckSkipped("no_dns_data")
    return data["records"].get(key)


@check("DNS-BIM-001",
       title="BIMI (Markenlogo in E-Mails) ## BIMI (brand logo in e-mail)",
       why="Mit BIMI zeigen Mail-Programme das Logo des Absenders an, wenn die Domain DMARC mit Durchsetzung nutzt. "
           "Das macht echte Mails erkennbar. ## With BIMI mail programs show the sender's logo when the domain uses "
           "DMARC with enforcement. This makes genuine mail recognisable.",
       method="Fragt den TXT-Eintrag default._bimi.<domain> ab (nur bei Domains mit Mail und DMARC-Eintrag). ## "
              "Queries the TXT record default._bimi.<domain> (only for domains with mail and a DMARC record).",
       logic="DMARC mit Durchsetzung vorhanden, aber kein BIMI-Eintrag: Info. ## DMARC with enforcement present but "
             "no BIMI record: info.",
       fix="TXT default._bimi: v=BIMI1; l=https://<domain>/logo.svg; a=<Zertifikat> veröffentlichen. ## Publish TXT "
           "default._bimi: v=BIMI1; l=https://<domain>/logo.svg; a=<certificate>.",
       refs=["https://bimigroup.org/implementation-guide/"], profiles="sd", source="network")
def bimi(snap):
    data = snap.extra.get("dns")
    if data is None:
        raise CheckSkipped("no_dns_data")
    records = data["records"]
    dmarc = [t for t in records.get("dmarc") or []]
    text = " ".join(dmarc).lower()
    if not dmarc or not re.search(r"p=(quarantine|reject)", text):
        return []
    bimi_records = records.get("bimi")
    if bimi_records is None:
        raise CheckSkipped("dns_bimi_unavailable")
    if any("v=bimi1" in r.lower() for r in bimi_records):
        return []
    return [F("DNS-BIM-001", S.INFO, snap.target.url, "Kein BIMI-Eintrag trotz DMARC mit Durchsetzung",
              "No BIMI record despite DMARC with enforcement")]


@check("DNS-DAN-001",
       title="DANE/TLSA (Zertifikat im DNS) ## DANE/TLSA (certificate in DNS)",
       why="DANE bindet das Zertifikat über DNSSEC an die Domain und schützt so vor falsch ausgestellten Zertifikaten. "
           "Für Webseiten wird es von Browsern nicht ausgewertet, für Mailserver ist es verbreitet. ## DANE binds "
           "the certificate to the domain through DNSSEC and protects against wrongly issued certificates. "
           "Browsers do not evaluate it for websites, it is common for mail servers.",
       method="Fragt den TLSA-Eintrag _443._tcp.<host> ab und meldet nur, wenn die Domain mit DNSSEC signiert ist "
              "und der Eintrag fehlt oder nicht zum Zertifikat gehören kann. ## Queries the TLSA record "
              "_443._tcp.<host> and reports only when the domain is signed with DNSSEC and the record is missing.",
       logic="DNSSEC aktiv, TLSA vorhanden: Info (Hinweis, dass Browser es ignorieren). Sonst nichts. ## DNSSEC "
             "active, TLSA present: info (browsers ignore it). Otherwise nothing.",
       fix="Nur wenn gewünscht: TLSA-Eintrag mit dem Zertifikatshash veröffentlichen und bei jedem "
           "Zertifikatswechsel aktualisieren. ## Only if wanted: publish a TLSA record with the certificate hash "
           "and update it at every certificate change.",
       refs=["https://www.rfc-editor.org/rfc/rfc6698"], profiles="sd", source="network")
def dane(snap):
    ds = _dns_records(snap, "ds")
    tlsa = _dns_records(snap, "tlsa")
    if ds is None or tlsa is None:
        raise CheckSkipped("dns_dane_unavailable")
    if ds and tlsa:
        return [F("DNS-DAN-001", S.INFO, snap.target.url,
                  "Ein TLSA-Eintrag ist vorhanden; Browser werten DANE nicht aus und ein falscher Hash stört nur Mailserver und DANE-Clients",
                  "A TLSA record is present; browsers do not evaluate DANE and a wrong hash only affects mail servers and DANE clients",
                  tlsa[0][:80])]
    return []
