from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urljoin, urlsplit

from ..core.registry import check
from ._util import F, S

GOOGLE = "https://developers.google.com/search/docs/"


@check("SEO-MET-001",
       title="Title und Meta-Description ## Title and meta description",
       why="Title und Description erscheinen in den Suchergebnissen. Fehlende, zu lange oder doppelte Texte "
           "senken Klickrate und Eindeutigkeit der Seiten. ## Title and description appear in search results. "
           "Missing, too long or duplicate texts reduce click-through rate and page distinctiveness.",
       method="Misst Länge von title (10 bis 60 Zeichen) und description (50 bis 160 Zeichen) und sucht doppelte Titel "
              "im Crawl. ## Measures length of title (10 to 60 characters) and description (50 to 160 characters) "
              "and looks for duplicate titles in the crawl.",
       logic="Description fehlt: Warnung. Länge außerhalb des Bereichs oder Duplikat: Hinweis. ## "
             "Missing description: warning. Length out of range or duplicate: note.",
       fix="Eindeutigen Titel und eine aussagekräftige Description je Seite schreiben. ## "
           "Write a unique title and a meaningful description per page.",
       refs=[GOOGLE + "appearance/title-link", GOOGLE + "appearance/snippet"], profiles="sd")
def title_desc(snap):
    out, titles = [], defaultdict(list)
    for pg in snap.docs():
        t = pg.soup.title.get_text(strip=True) if pg.soup.title else ""
        if t:
            titles[t].append(pg.url)
            if not 10 <= len(t) <= 60:
                out.append(F("SEO-MET-001", S.NOTE, pg.url, "Titel-Länge außerhalb von 10 bis 60 Zeichen",
                             "Title length outside 10 to 60 characters", t[:80]))
        d = pg.soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        dc = str(d.get("content", "")).strip() if d else ""
        if not dc:
            out.append(F("SEO-MET-001", S.WARNING, pg.url, "Meta-Description fehlt", "Meta description missing"))
        elif not 50 <= len(dc) <= 160:
            out.append(F("SEO-MET-001", S.NOTE, pg.url, "Description-Länge außerhalb von 50 bis 160 Zeichen",
                         "Description length outside 50 to 160 characters", dc[:80]))
    for t, urls in titles.items():
        if len(urls) > 1:
            out.append(F("SEO-MET-001", S.NOTE, urls[0], f"Doppelter Titel auf {len(urls)} Seiten",
                         f"Duplicate title on {len(urls)} pages", t[:80]))
    return out


@check("SEO-CAN-001",
       title="Canonical-URL ## Canonical URL",
       why="Die Canonical-URL verhindert Duplicate Content und bündelt Ranking-Signale auf einer Variante. ## "
           "The canonical URL prevents duplicate content and consolidates ranking signals on one variant.",
       method="Liest link[rel=canonical] je Seite, prüft Anzahl und Host. ## Reads link[rel=canonical] per page, checks count and host.",
       logic="Mehrere: Warnung. Fehlt oder fremder Host: Hinweis. ## Multiple: warning. Missing or foreign host: note.",
       fix="Genau eine absolute Canonical-URL auf die bevorzugte Variante setzen. ## "
           "Set exactly one absolute canonical URL pointing to the preferred variant.",
       refs=[GOOGLE + "crawling-indexing/consolidate-duplicate-urls", "https://www.rfc-editor.org/rfc/rfc6596"], profiles="sd")
def canonical(snap):
    out = []
    for pg in snap.docs():
        links = [x for x in pg.soup.find_all("link", href=True) if "canonical" in (x.get("rel") or [])]
        if not links:
            out.append(F("SEO-CAN-001", S.NOTE, pg.url, "Keine Canonical-URL", "No canonical URL"))
        elif len(links) > 1:
            out.append(F("SEO-CAN-001", S.WARNING, pg.url, "Mehrere Canonical-URLs", "Multiple canonical URLs"))
        elif urlsplit(urljoin(pg.url, links[0]["href"])).hostname != urlsplit(pg.url).hostname:
            out.append(F("SEO-CAN-001", S.NOTE, pg.url, "Canonical zeigt auf anderen Host",
                         "Canonical points to another host", str(links[0]["href"])[:120]))
    return out


@check("SEO-ROB-001",
       title="Indexierungssperren (noindex, robots.txt) ## Indexing blocks (noindex, robots.txt)",
       why="Ein versehentliches noindex oder 'Disallow: /' entfernt Seiten aus der Suche. ## "
           "An accidental noindex or 'Disallow: /' removes pages from search.",
       method="Sucht meta robots, X-Robots-Tag und in robots.txt 'Disallow: /' für User-agent *. ## "
              "Looks for meta robots, X-Robots-Tag and 'Disallow: /' for user-agent * in robots.txt.",
       logic="noindex auf der Startseite oder Komplettsperre: Fehler, auf Unterseiten: Warnung. ## "
             "noindex on the start page or full block: error, on sub pages: warning.",
       fix="noindex/Disallow nur dort setzen, wo es gewollt ist. ## Use noindex/Disallow only where intended.",
       refs=[GOOGLE + "crawling-indexing/robots/intro", "https://www.rfc-editor.org/rfc/rfc9309"], profiles="sd")
def robots(snap):
    out = []
    for pg in snap.docs():
        meta = pg.soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
        val = (str(meta.get("content", "")) if meta else "") + " " + pg.headers.get("x-robots-tag", "")
        if "noindex" in val.lower():
            out.append(F("SEO-ROB-001", S.ERROR if pg is snap.pages[0] else S.WARNING, pg.url,
                         "Seite ist auf noindex gesetzt", "Page is set to noindex", val.strip()[:80]))
    if snap.robots_txt:
        star = False
        for line in snap.robots_txt.splitlines():
            line = line.split("#")[0].strip().lower()
            if line.startswith("user-agent:"):
                star = line.split(":", 1)[1].strip() == "*"
            elif star and re.fullmatch(r"disallow:\s*/", line):
                out.append(F("SEO-ROB-001", S.ERROR, snap.target.url, "robots.txt sperrt die gesamte Website",
                             "robots.txt blocks the entire website"))
                break
    return out
