"""Prüfungen mit Daten externer Dienste (nur mit eingeschaltetem Schalter): Safe Browsing (core/probe_safebrowsing.py)
und PageSpeed Insights (core/probe_psi.py). Ohne Schalter oder ohne Antwort gelten sie als nicht ausgeführt."""
from __future__ import annotations

from ..core.registry import check
from ._util import CheckSkipped, F, S

_THREATS = {
    "MALWARE": (S.CRITICAL, "Schadsoftware", "malware"),
    "SOCIAL_ENGINEERING": (S.CRITICAL, "Phishing oder Social Engineering", "phishing or social engineering"),
    "UNWANTED_SOFTWARE": (S.ERROR, "unerwünschte Software", "unwanted software"),
    "POTENTIALLY_HARMFUL_APPLICATION": (S.ERROR, "potenziell schädliche Anwendung", "potentially harmful application"),
}


@check("SEC-SBR-001",
       title="Google Safe Browsing ## Google Safe Browsing",
       why="Steht eine Adresse auf den Listen von Google für Schadsoftware oder Phishing, warnen Browser Besucher mit einer "
           "roten Seite und die Website verliert fast den gesamten Verkehr. Oft merken Betreiber eine Infektion erst dadurch. "
           "## If an address is on Google's lists for malware or phishing, browsers warn visitors with a red page and the "
           "website loses almost all traffic. Operators often notice an infection only because of that.",
       method="Nur mit eingeschaltetem Schalter und eigenem API-Schlüssel (Seite Externe Dienste, Standard: aus). Sendet "
              "höchstens 5 Adressen der geprüften Website ohne Parameter an Google (Safe Browsing, Ggedächtnisbasiert v4 "
              "threatMatches:find, ungeprüft) und wertet die Treffer aus. Google sieht die IP-Adresse des Nutzers. Fehlt der "
              "Schlüssel oder antwortet der Dienst nicht, gilt die Prüfung als nicht ausgeführt. ## Only with the switch on "
              "and your own API key (External services page, default: off). Sends at most 5 addresses of the checked website "
              "without parameters to Google (Safe Browsing, v4 threatMatches:find from memory, unverified) and evaluates the "
              "matches. Google sees the user's IP address. Without a key or if the service does not answer, the check counts "
              "as not executed.",
       logic="Schadsoftware oder Phishing: kritisch. Unerwünschte oder potenziell schädliche Software: Fehler. Kein Treffer: "
             "kein Befund. ## Malware or phishing: critical. Unwanted or potentially harmful software: error. No match: no "
             "finding.",
       fix="Die Website bereinigen (Dateien und Datenbank prüfen, Zugangsdaten ändern) und danach in der Search Console eine "
           "Überprüfung beantragen. ## Clean the website (check files and database, change credentials) and then request a "
           "review in Search Console.",
       refs=["https://developers.google.com/safe-browsing", "https://transparencyreport.google.com/safe-browsing/search"],
       profiles="sd", source="network")
def safe_browsing(snap):
    data = snap.extra.get("safebrowsing")
    if data is None:
        raise CheckSkipped("no_safebrowsing_data")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    out = []
    for match in data.get("matches") or []:
        severity, de, en = _THREATS.get(match.get("type"), (S.ERROR, "Bedrohung", "threat"))
        out.append(F("SEC-SBR-001", severity, snap.target.url, f"Google Safe Browsing meldet {de}",
                     f"Google Safe Browsing reports {en}", f"{match.get('type')} {match.get('url', '')}".strip()))
    return out


FIELD_NAMES = {"LARGEST_CONTENTFUL_PAINT_MS": "LCP", "CUMULATIVE_LAYOUT_SHIFT_SCORE": "CLS",
               "INTERACTION_TO_NEXT_PAINT": "INP", "FIRST_CONTENTFUL_PAINT_MS": "FCP",
               "EXPERIMENTAL_TIME_TO_FIRST_BYTE": "TTFB", "FIRST_INPUT_DELAY_MS": "FID"}
_CATEGORY_LABELS = {"seo": ("SEO", "SEO"), "accessibility": ("Barrierefreiheit", "accessibility"),
                    "best_practices": ("Best Practices", "best practices")}


@check("SEO-PSI-001",
       title="PageSpeed Insights (Lighthouse und Felddaten) ## PageSpeed Insights (Lighthouse and field data)",
       why="Google bewertet Ladegeschwindigkeit und Stabilität mit Daten echter Besucher (CrUX) und einer Labormessung "
           "(Lighthouse). Schlechte Werte kosten Ranking und Besucher. ## Google rates loading speed and stability with data "
           "from real visitors (CrUX) and a lab measurement (Lighthouse). Poor values cost ranking and visitors.",
       method="Nur mit eingeschaltetem Schalter (Seite Externe Dienste, Standard: aus). Eine Abfrage an den PageSpeed-Dienst "
              "von Google (mobil) mit der Adresse der Startseite. Google ruft die Seite selbst ab und sieht die IP-Adresse des "
              "Nutzers. Ausgewertet werden die Lighthouse-Kategorien und die CrUX-Felddaten, falls es welche gibt. Die Labormessung "
              "ist simuliert. Ohne Schlüssel gilt ein kleines Kontingent (bei HTTP 429 gilt die Prüfung als nicht ausgeführt). Die "
              "Antwortfelder stammen aus dem Gedächtnis und sind ungeprüft. ## Only with the switch on (External services page, "
              "default: off). One request to Google's PageSpeed service (mobile) with the address of the home page. Google fetches "
              "the page itself and sees the user's IP address. Evaluates the Lighthouse categories and the CrUX field data, if "
              "there is any. The lab measurement is simulated. Without a key a small quota applies (on HTTP 429 the check counts as "
              "not executed). The response fields come from memory and are unverified.",
       logic="Performance unter 50: Warnung, unter 90: Hinweis. Felddaten LANGSAM: Warnung, DURCHSCHNITTLICH: Hinweis. Keine "
             "Felddaten oder SEO, Barrierefreiheit, Best Practices unter 90: Info. ## Performance below 50: warning, below 90: "
             "note. Field data SLOW: warning, AVERAGE: note. No field data or SEO, accessibility, best practices below 90: info.",
       fix="Bilder verkleinern, Skripte aufschieben, Schriften vorladen, Komprimierung und Caching aktivieren; den Bericht auf "
           "pagespeed.web.dev lesen. ## Shrink images, defer scripts, preload fonts, enable compression and caching; read the "
           "report at pagespeed.web.dev.",
       refs=["https://developers.google.com/speed/docs/insights/v5/about", "https://web.dev/articles/vitals"],
       profiles="sd", source="network")
def pagespeed(snap):
    data = snap.extra.get("psi")
    if data is None:
        raise CheckSkipped("no_psi_data")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    url, out = snap.target.url, []
    scores = data.get("scores") or {}
    perf = scores.get("performance")
    if perf is not None and perf < 50:
        out.append(F("SEO-PSI-001", S.WARNING, url, f"Lighthouse-Performance (mobil, simuliert) nur {perf} von 100",
                     f"Lighthouse performance (mobile, simulated) only {perf} of 100"))
    elif perf is not None and perf < 90:
        out.append(F("SEO-PSI-001", S.NOTE, url, f"Lighthouse-Performance (mobil, simuliert) {perf} von 100",
                     f"Lighthouse performance (mobile, simulated) {perf} of 100"))
    for key, (de, en) in _CATEGORY_LABELS.items():
        value = scores.get(key)
        if value is not None and value < 90:
            out.append(F("SEO-PSI-001", S.INFO, url, f"Lighthouse {de}: {value} von 100",
                         f"Lighthouse {en}: {value} of 100"))
    field = data.get("field") or {}
    if not field:
        out.append(F("SEO-PSI-001", S.INFO, url, "Keine Felddaten (CrUX) für diese Adresse, zu wenig Besucher",
                     "No field data (CrUX) for this address, too few visitors"))
    for name, metric in sorted(field.items()):
        label = FIELD_NAMES.get(name, name[:30])
        category = str(metric.get("category", "")).upper()
        evidence = f"p75={metric.get('percentile')}"
        if category == "SLOW":
            out.append(F("SEO-PSI-001", S.WARNING, url, f"Felddaten echter Besucher: {label} ist langsam",
                         f"Field data of real visitors: {label} is slow", evidence))
        elif category == "AVERAGE":
            out.append(F("SEO-PSI-001", S.NOTE, url, f"Felddaten echter Besucher: {label} ist durchschnittlich",
                         f"Field data of real visitors: {label} is average", evidence))
    return out
