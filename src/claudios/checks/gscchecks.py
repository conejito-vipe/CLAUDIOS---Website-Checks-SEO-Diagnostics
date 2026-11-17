"""Prüfungen mit Daten der Google Search Console. Die Daten liefert die Probe core/probe_gsc.py.
'Aktiv' heißt bei den Prüfungen mit Schnittstelle nur: sie brauchen Stufe 2. An die geprüfte Website geht nichts."""
from __future__ import annotations

from ..core.crawler import norm
from ..core.registry import check
from ._util import CheckSkipped, F, S
from .seo_more import _noindex

GOOGLE = "https://developers.google.com/webmaster-tools/"


def _data(snap) -> dict:
    data = snap.extra.get("gsc")
    if data is None:
        raise CheckSkipped("no_gsc_data")
    return data


@check("GSC-IDX-001",
       title="Indexstatus laut Google (URL-Inspektion) ## Index status according to Google (URL inspection)",
       why="Eine Seite kann technisch sauber sein und trotzdem nicht im Google-Index stehen, etwa wegen einer Sperre in "
           "der robots.txt, eines noindex oder weil Google eine andere Adresse als kanonisch wählt. Nur Google weiß, "
           "was es wirklich sieht. ## A page can be technically clean and still not be in the Google index, for "
           "example because of a robots.txt block, a noindex or because Google chooses a different address as "
           "canonical. Only Google knows what it really sees.",
       method="Nur Stufe 2 mit Anmeldung bei Google. Fragt für bis zu 10 Seiten der Stichprobe die URL-Inspektion der "
              "Search Console ab (eine Anfrage pro Sekunde) und wertet Urteil, Abdeckung, robots.txt-Status, "
              "Indexierungssperren, Abrufstatus und Canonical aus. Die Daten haben etwa 2 bis 3 Tage Verzug und es "
              "gibt Tageskontingente. ## Level 2 only, with Google sign-in. Queries the Search Console URL "
              "inspection for up to 10 pages of the sample (one request per second) and evaluates verdict, "
              "coverage, robots.txt status, indexing blocks, fetch status and canonical. The data lags by about 2 "
              "to 3 days and daily quotas apply.",
       logic="Urteil FAIL, robots.txt-Sperre, Indexierungssperre, Abruf nicht erfolgreich: Warnung. Urteil NEUTRAL, "
             "abweichender Canonical: Hinweis. ## Verdict FAIL, robots.txt block, indexing block, fetch not "
             "successful: warning. Verdict NEUTRAL, differing canonical: note.",
       fix="Die im Beleg genannte Ursache beheben (robots.txt, noindex, Canonical) und die Seite in der Search Console "
           "erneut zur Indexierung anfordern. ## Fix the cause named in the evidence (robots.txt, noindex, canonical) "
           "and request indexing again in Search Console.",
       refs=[GOOGLE + "v1/reference/urlInspection.index/inspect", "https://support.google.com/webmasters/"],
       profiles="sd", kind="active", source="gsc")
def indexing(snap):
    api = _data(snap)["api"]
    if api is None:
        raise CheckSkipped("no_gsc_api_data")
    if api["inspections"] is None:
        raise CheckSkipped("gsc_inspection_unavailable")
    out = []
    for rec in api["inspections"]:
        url, coverage = rec["url"], rec["coverage"]
        if rec["verdict"] == "FAIL":
            out.append(F("GSC-IDX-001", S.WARNING, url, "Google hat die Seite nicht im Index",
                         "Google has not indexed the page", coverage))
        elif rec["verdict"] == "NEUTRAL":
            out.append(F("GSC-IDX-001", S.NOTE, url, "Google hat die Seite bewusst oder vorerst nicht indexiert",
                         "Google has not indexed the page, on purpose or for now", coverage))
        if rec["robots"] == "DISALLOWED":
            out.append(F("GSC-IDX-001", S.WARNING, url, "Die robots.txt sperrt die Seite für Google",
                         "robots.txt blocks the page for Google"))
        if rec["indexing"].startswith("BLOCKED"):
            out.append(F("GSC-IDX-001", S.WARNING, url, "Die Seite ist für die Indexierung gesperrt",
                         "The page is blocked from indexing", rec["indexing"]))
        if rec["fetch"] not in ("", "SUCCESSFUL", "PAGE_FETCH_STATE_UNSPECIFIED"):
            out.append(F("GSC-IDX-001", S.WARNING, url, "Google konnte die Seite nicht erfolgreich abrufen",
                         "Google could not fetch the page successfully", rec["fetch"]))
        google, user = rec["google_canonical"], rec["user_canonical"]
        if google and user and google != user:
            out.append(F("GSC-IDX-001", S.NOTE, url, "Google wählt einen anderen Canonical als angegeben",
                         "Google chooses a different canonical than declared", f"{user} → {google}"))
    return out


@check("GSC-SMP-001",
       title="Sitemap-Status laut Google ## Sitemap status according to Google",
       why="Google zeigt in der Search Console, ob es eine eingereichte Sitemap lesen konnte und welche Fehler es darin "
           "fand. Eine fehlerhafte oder fehlende Sitemap verzögert die Entdeckung neuer Seiten. ## Google shows in "
           "Search Console whether it could read a submitted sitemap and which errors it found. A faulty or missing "
           "sitemap delays the discovery of new pages.",
       method="Nur Stufe 2 mit Anmeldung bei Google. Liest die in der Search Console eingereichten Sitemaps der Property "
              "und wertet Fehler, Warnungen und den Verarbeitungsstatus aus. ## Level 2 only, with Google sign-in. "
              "Reads the sitemaps submitted for the property in Search Console and evaluates errors, warnings and "
              "processing status.",
       logic="Fehler laut Google: Fehler. Warnungen und keine eingereichte Sitemap: Hinweis. Noch in Verarbeitung: "
             "Info. ## Errors according to Google: error. Warnings and no submitted sitemap: note. Still being "
             "processed: info.",
       fix="Sitemap korrigieren und in der Search Console erneut einreichen. ## Fix the sitemap and submit it again "
           "in Search Console.",
       refs=[GOOGLE + "v1/sitemaps", "https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview"],
       profiles="sd", kind="active", source="gsc")
def sitemaps(snap):
    api = _data(snap)["api"]
    if api is None:
        raise CheckSkipped("no_gsc_api_data")
    if api["sitemaps"] is None:
        raise CheckSkipped("gsc_sitemaps_unavailable")
    url = snap.target.url
    if not api["sitemaps"]:
        return [F("GSC-SMP-001", S.NOTE, url, "In der Search Console ist keine Sitemap eingereicht",
                  "No sitemap is submitted in Search Console")]
    out = []
    for rec in api["sitemaps"]:
        if rec["errors"] > 0:
            out.append(F("GSC-SMP-001", S.ERROR, rec["path"], f"Google meldet {rec['errors']} Fehler in der Sitemap",
                         f"Google reports {rec['errors']} errors in the sitemap"))
        if rec["warnings"] > 0:
            out.append(F("GSC-SMP-001", S.NOTE, rec["path"], f"Google meldet {rec['warnings']} Warnungen zur Sitemap",
                         f"Google reports {rec['warnings']} warnings for the sitemap"))
        if rec["pending"]:
            out.append(F("GSC-SMP-001", S.INFO, rec["path"], "Die Sitemap wird noch von Google verarbeitet",
                         "The sitemap is still being processed by Google"))
    return out


@check("GSC-PRF-001",
       title="Seiten im Vergleich mit der Google-Suche ## Pages compared with Google Search",
       why="Seiten, die einen Fehler liefern, aber noch Impressionen in der Suche haben, verlieren Besucher und Ansehen. "
           "Gecrawlte Seiten ganz ohne Impressionen sind oft nicht auffindbar oder wertlos. Nur die Search-Console-Daten "
           "zeigen diesen Zusammenhang. ## Pages that return an error but still have impressions in search lose "
           "visitors and reputation. Crawled pages with no impressions at all are often not findable or worthless. "
           "Only the Search Console data shows this connection.",
       method="Gleicht die gecrawlten Seiten mit den Seiten-Impressionen der letzten 28 Tage ab. Quelle ist die "
              "Search-Console-Schnittstelle (Stufe 2, höchstens die 1.000 besten Seiten) oder ein CSV-Import. Es werden "
              "nur Adressen und Zahlen verwendet, nie Suchbegriffe. Fehlt die Datenquelle, gilt die Prüfung als nicht "
              "ausgeführt. ## Compares the crawled pages with the page impressions of the last 28 days. The source is "
              "the Search Console interface (level 2, at most the 1,000 best pages) or a CSV import. Only addresses "
              "and numbers are used, never search terms. Without a data source the check counts as not executed.",
       logic="Fehlerseite mit Impressionen: Warnung. Gecrawlte Seiten ohne Impressionen: Info (kein Beweis für ein "
             "Problem). ## Error page with impressions: warning. Crawled pages without impressions: info (no proof of "
             "a problem).",
       fix="Fehlerseiten per 301 auf passende Inhalte weiterleiten oder entfernen und aus der Sitemap nehmen; Seiten ohne "
           "Impressionen intern verlinken oder verbessern. ## Redirect error pages with a 301 to matching content or "
           "remove them and drop them from the sitemap; link to or improve pages without impressions.",
       refs=[GOOGLE + "v1/reference/searchanalytics/query", "https://support.google.com/webmasters/answer/7576553"],
       profiles="sd", source="gsc")
def performance(snap):
    data = _data(snap)
    if data["pages"] is None:
        raise CheckSkipped("no_gsc_data")
    source = "Search Console" if data["source"] == "api" else "CSV"
    known = {norm(p["url"]): p for p in data["pages"]}
    out = []
    for pg in snap.pages:
        broken = pg.error is not None or (pg.status is not None and pg.status >= 400)
        rec = known.get(norm(pg.url))
        if broken and rec and rec["impressions"] > 0:
            out.append(F("GSC-PRF-001", S.WARNING, pg.url,
                         f"Fehlerseite hat noch {rec['impressions']} Impressionen in der Suche (Quelle: {source})",
                         f"Error page still has {rec['impressions']} impressions in search (source: {source})"))
    if not data["truncated"]:
        missing = [pg for pg in snap.docs()
                   if pg.status == 200 and norm(pg.url) not in known and not _noindex(pg)]
        if missing:
            out.append(F("GSC-PRF-001", S.INFO, missing[0].url,
                         f"{len(missing)} gecrawlte Seite(n) ohne Impressionen in 28 Tagen (Quelle: {source})",
                         f"{len(missing)} crawled page(s) without impressions in 28 days (source: {source})"))
    return out
