"""Datenschutz-Indizien aus dem ersten Seitenabruf. Technische Hinweise, keine Rechtsberatung."""
from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlsplit

from ..core.registry import check
from ._util import F, S

GDPR = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"
DDG5 = "https://www.gesetze-im-internet.de/ddg/__5.html"
EDPB_COOKIES = "https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines_en"

_IMPRINT = re.compile(r"impressum|imprint|legal[\s-]*notice|anbieterkennung|rechtliche[\s-]*hinweise", re.I)
_PRIVACY = re.compile(r"datenschutz|privacy|data[\s-]*protection", re.I)
_TRACKER_COOKIE = re.compile(
    r"^(_ga(_.*)?|_gid|_gat.*|_gcl_.*|_fbp|_fbc|fr|_hj.*|ide|test_cookie|_clck|_clsk|_uetsid|_uetvid|muid|"
    r"_pin_unauth|_ttp|li_.*|_pk_.*|ajs_.*)$", re.I)

# (Host-Endung, Name, Kategorie)
SERVICES = (
    ("fonts.googleapis.com", "Google Fonts", "font"), ("fonts.gstatic.com", "Google Fonts", "font"),
    ("use.typekit.net", "Adobe Fonts", "font"),
    ("youtube.com", "YouTube", "video"), ("youtube-nocookie.com", "YouTube (nocookie)", "video"),
    ("vimeo.com", "Vimeo", "video"),
    ("maps.googleapis.com", "Google Maps", "map"), ("maps.gstatic.com", "Google Maps", "map"),
    ("openstreetmap.org", "OpenStreetMap", "map"), ("api.mapbox.com", "Mapbox", "map"),
    ("recaptcha.net", "reCAPTCHA", "captcha"), ("hcaptcha.com", "hCaptcha", "captcha"),
    ("google-analytics.com", "Google Analytics", "tracking"),
    ("googletagmanager.com", "Google Tag Manager", "tracking"),
    ("doubleclick.net", "Google Ads (DoubleClick)", "tracking"),
    ("googlesyndication.com", "Google AdSense", "tracking"),
    ("connect.facebook.net", "Meta Pixel / Facebook", "tracking"),
    ("hotjar.com", "Hotjar", "tracking"), ("clarity.ms", "Microsoft Clarity", "tracking"),
    ("analytics.tiktok.com", "TikTok Pixel", "tracking"), ("snap.licdn.com", "LinkedIn Insight", "tracking"),
    ("ads-twitter.com", "X/Twitter Ads", "tracking"),
    ("platform.twitter.com", "X/Twitter", "social"), ("platform.instagram.com", "Instagram", "social"),
    ("instagram.com", "Instagram", "social"), ("facebook.com", "Facebook", "social"),
    ("platform.linkedin.com", "LinkedIn", "social"), ("tiktok.com", "TikTok", "social"),
)
# Dienste, die oft in Inline-Skripten geladen werden (Stichwort, Name, Kategorie)
_INLINE = (
    ("googletagmanager.com", "Google Tag Manager", "tracking"),
    ("google-analytics.com", "Google Analytics", "tracking"),
    ("connect.facebook.net", "Meta Pixel / Facebook", "tracking"),
    ("static.hotjar.com", "Hotjar", "tracking"), ("clarity.ms", "Microsoft Clarity", "tracking"),
)
_CMP = (
    ("usercentrics", "Usercentrics"), ("cookiebot", "Cookiebot"), ("onetrust", "OneTrust"),
    ("cookielaw.org", "OneTrust"), ("borlabs", "Borlabs Cookie"), ("complianz", "Complianz"),
    ("cmplz", "Complianz"), ("cookieyes", "CookieYes"), ("klaro", "Klaro"), ("iubenda", "iubenda"),
    ("consentmanager", "consentmanager"), ("didomi", "Didomi"), ("quantcast", "Quantcast Choice"),
    ("termly", "Termly"), ("osano", "Osano"), ("cookieconsent", "Cookie Consent"),
    ("cookie-notice", "Cookie Notice"), ("cookie-law-info", "Cookie Law Info"),
)
_TAGS = (("script", "src"), ("link", "href"), ("iframe", "src"), ("img", "src"), ("source", "src"),
         ("video", "src"), ("audio", "src"), ("embed", "src"), ("object", "data"))
_RESOURCE_RELS = {"stylesheet", "preload", "prefetch", "preconnect", "dns-prefetch", "icon", "modulepreload"}
CAT_DE = {"font": "Schriften", "video": "Video", "map": "Karten", "tracking": "Tracking/Werbung",
          "social": "Soziale Netzwerke", "captcha": "CAPTCHA"}
CAT_EN = {"font": "fonts", "video": "video", "map": "maps", "tracking": "tracking/advertising",
          "social": "social networks", "captcha": "CAPTCHA"}


def service_of(url: str) -> tuple[str, str] | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    if not host:
        return None
    if host.endswith("google.com") and path.startswith("/maps"):
        return "Google Maps", "map"
    if (host.endswith("google.com") or host.endswith("gstatic.com")) and path.startswith("/recaptcha"):
        return "reCAPTCHA", "captcha"
    for suffix, name, category in SERVICES:
        if host == suffix or host.endswith("." + suffix):
            return name, category
    return None


def detect_services(snap) -> dict[str, tuple[str, str]]:
    """Name -> (Kategorie, erste Seite, auf der der Dienst gefunden wurde)."""
    found: dict[str, tuple[str, str]] = {}
    for pg in snap.docs():
        soup = pg.soup
        for tag, attr in _TAGS:
            for element in soup.find_all(tag):
                if tag == "link":
                    rels = {r.lower() for r in (element.get("rel") or [])}
                    if not rels & _RESOURCE_RELS:
                        continue
                value = str(element.get(attr, "")).strip()
                if not value:
                    continue
                hit = service_of(urljoin(pg.url, value))
                if hit is not None:
                    found.setdefault(hit[0], (hit[1], pg.url))
        for script in soup.find_all("script"):
            if script.get("src"):
                continue
            body = (script.string or script.get_text() or "").lower()
            for needle, name, category in _INLINE:
                if needle in body:
                    found.setdefault(name, (category, pg.url))
    return found


def detect_cmp(snap) -> list[str]:
    found: list[str] = []
    for pg in snap.docs():
        low = pg.html.lower()
        for needle, name in _CMP:
            if needle in low and name not in found:
                found.append(name)
    return found


def _german_site(snap) -> bool:
    if snap.target.host.endswith((".de", ".at", ".ch")):
        return True
    docs = snap.docs()
    if not docs:
        return False
    root = docs[0].soup.find("html")
    return bool(root) and str(root.get("lang", "")).lower().startswith("de")


@check("PRV-LEG-001",
       title="Impressum und Datenschutzerklärung verlinkt ## Legal notice and privacy policy linked",
       why="In Deutschland, Österreich und der Schweiz ist ein erreichbares Impressum für geschäftsmäßige Angebote "
           "Pflicht, und die Datenschutz-Grundverordnung verlangt Informationen über die Datenverarbeitung. "
           "Fehlende Angaben sind ein häufiger Abmahngrund. ## In Germany, Austria and Switzerland an accessible "
           "legal notice (imprint) is mandatory for commercial sites, and the GDPR requires information about "
           "data processing. Missing details are a common reason for warning letters.",
       method="Sucht auf allen gecrawlten Seiten nach Links, deren Text, Beschriftung oder Pfad auf Impressum "
              "(Impressum, Imprint, Legal Notice) oder Datenschutz (Datenschutz, Privacy) hindeutet. Als "
              "deutschsprachig gilt eine Seite mit Endung .de, .at, .ch oder lang=de. Es wird nur geprüft, ob "
              "ein Link existiert, nicht der Inhalt der Seiten. ## Searches all crawled pages for links whose "
              "text, label or path suggests a legal notice (Impressum, Imprint, Legal Notice) or privacy "
              "(Datenschutz, Privacy). A site counts as German-speaking with the ending .de, .at, .ch or lang=de. "
              "Only the existence of a link is checked, not the content of the pages.",
       logic="Deutschsprachige Seite ohne Link: Warnung. Sonst fehlendes Impressum: Info, fehlende "
             "Datenschutzerklärung: Hinweis. ## German-speaking site without link: warning. Otherwise missing "
             "legal notice: info, missing privacy policy: note.",
       fix="Auf jeder Seite (meist im Footer) Links auf Impressum und Datenschutzerklärung setzen. ## "
           "Add links to the legal notice and the privacy policy on every page (usually in the footer).",
       refs=[GDPR, DDG5], profiles="sd")
def legal_links(snap):
    docs = snap.docs()
    if not docs:
        return []
    imprint = privacy = False
    for pg in docs:
        for a in pg.soup.find_all("a", href=True):
            label = " ".join((a.get_text(" ", strip=True), str(a.get("aria-label", "")), str(a.get("title", "")),
                              unquote(urlsplit(str(a["href"])).path)))
            imprint = imprint or bool(_IMPRINT.search(label))
            privacy = privacy or bool(_PRIVACY.search(label))
    strict = _german_site(snap)
    url = snap.pages[0].url
    out = []
    if not imprint:
        out.append(F("PRV-LEG-001", S.WARNING if strict else S.INFO, url, "Kein Impressum-Link gefunden",
                     "No legal-notice (imprint) link found"))
    if not privacy:
        out.append(F("PRV-LEG-001", S.WARNING if strict else S.NOTE, url,
                     "Kein Link auf die Datenschutzerklärung gefunden", "No privacy-policy link found"))
    return out


@check("PRV-EXT-001",
       title="Externe Dienste beim ersten Aufruf ## Third-party services on first load",
       why="Werden Schriften, Videos, Karten oder Trackingdienste von Fremdservern geladen, erhalten diese die "
           "IP-Adresse des Besuchers, bevor er etwas entscheiden konnte. In Deutschland gab es dazu bereits "
           "Gerichtsentscheidungen, und Tracking braucht in der Regel eine Einwilligung. ## When fonts, videos, "
           "maps or tracking services are loaded from third-party servers, they receive the visitor's IP "
           "address before the visitor could decide anything. In Germany there have already been court "
           "decisions on this, and tracking usually requires consent.",
       method="Erkennt bekannte Dienste (Google Fonts, YouTube, Vimeo, Google Maps, OpenStreetMap, reCAPTCHA, "
              "Google Analytics, Tag Manager, Meta Pixel, Hotjar, soziale Netzwerke u. a.) an den Adressen von "
              "Skripten, Stilen, iFrames und Medien sowie an Stichwörtern in Inline-Skripten. Nachgeladene "
              "Inhalte sieht nur ein Browser und werden hier nicht erfasst. Technischer Hinweis, keine "
              "Rechtsberatung. ## Detects known services (Google Fonts, YouTube, Vimeo, Google Maps, "
              "OpenStreetMap, reCAPTCHA, Google Analytics, Tag Manager, Meta Pixel, Hotjar, social networks and "
              "others) from the addresses of scripts, styles, iframes and media and from keywords in inline "
              "scripts. Content loaded later is only visible to a browser and is not covered here. Technical "
              "indication, not legal advice.",
       logic="Tracking- oder Werbedienst: Warnung. Schriften, Video, Karten, soziale Netzwerke, CAPTCHA: "
             "Hinweis. Je Dienst ein Befund. ## Tracking or advertising service: warning. Fonts, video, maps, "
             "social networks, CAPTCHA: note. One finding per service.",
       fix="Dienste erst nach Einwilligung laden, Schriften selbst hosten, für Videos und Karten "
           "datensparsame Einbettungen oder Zwei-Klick-Lösungen nutzen. ## Load services only after consent, "
           "self-host fonts, and use privacy-friendly embeds or two-click solutions for videos and maps.",
       refs=[GDPR, "https://eur-lex.europa.eu/eli/dir/2002/58/oj"], profiles="sd")
def external_services(snap):
    out = []
    for name, (category, url) in sorted(detect_services(snap).items()):
        severity = S.WARNING if category == "tracking" else S.NOTE
        out.append(F("PRV-EXT-001", severity, url,
                     f"Externer Dienst eingebunden: {name} ({CAT_DE[category]})",
                     f"Third-party service embedded: {name} ({CAT_EN[category]})", name))
    return out


@check("PRV-COK-001",
       title="Cookies beim ersten Aufruf ## Cookies on first load",
       why="Cookies, die nicht technisch notwendig sind (Statistik, Werbung), dürfen in der Regel erst nach "
           "Einwilligung gesetzt werden. Setzt der Server sie schon beim ersten Aufruf, geschieht das ohne "
           "Wahlmöglichkeit. ## Cookies that are not technically necessary (statistics, advertising) may "
           "usually only be set after consent. If the server sets them on the first request, this happens "
           "without any choice.",
       method="Wertet die Namen der Set-Cookie-Header aller gecrawlten Antworten aus (Werte werden nie "
              "gespeichert) und vergleicht sie mit bekannten Tracking-Cookies (_ga, _gid, _fbp, _hj*, _pk_* u. a.). "
              "Cookies, die per JavaScript gesetzt werden, sieht nur ein Browser. ## Evaluates the names of the "
              "Set-Cookie headers of all crawled responses (values are never stored) and compares them with known "
              "tracking cookies (_ga, _gid, _fbp, _hj*, _pk_* and others). Cookies set by JavaScript are only "
              "visible to a browser.",
       logic="Bekanntes Tracking-Cookie: Warnung. Andere Cookies beim ersten Aufruf: Info. ## Known tracking "
             "cookie: warning. Other cookies on first load: info.",
       fix="Nicht notwendige Cookies erst nach aktiver Einwilligung setzen. ## Set non-essential cookies only "
           "after active consent.",
       refs=["https://eur-lex.europa.eu/eli/dir/2002/58/oj", GDPR], profiles="sd")
def cookies_before_consent(snap):
    names: list[str] = []
    trackers: list[str] = []
    for pg in snap.pages:
        for cookie in pg.cookies:
            if cookie.name in names:
                continue
            names.append(cookie.name)
            if _TRACKER_COOKIE.match(cookie.name):
                trackers.append(cookie.name)
    if not names:
        return []
    url = snap.pages[0].url
    out = []
    if trackers:
        listed = ", ".join(trackers[:5])
        out.append(F("PRV-COK-001", S.WARNING, url, f"Tracking-Cookie beim ersten Aufruf gesetzt: {listed}",
                     f"Tracking cookie set on first load: {listed}", listed))
    others = [n for n in names if n not in trackers]
    if others:
        out.append(F("PRV-COK-001", S.INFO, url, f"{len(others)} Cookie(s) beim ersten Aufruf ohne Einwilligung gesetzt",
                     f"{len(others)} cookie(s) set on first load without consent", ", ".join(others[:5])))
    return out


@check("PRV-CMP-001",
       title="Einwilligungslösung (Cookie-Banner) ## Consent solution (cookie banner)",
       why="Wer Tracking oder Fremddienste nutzt, braucht meist eine Einwilligungslösung, die das Laden bis zur "
           "Entscheidung verhindert und das Ablehnen so leicht macht wie das Zustimmen. ## Anyone using "
           "tracking or third-party services usually needs a consent solution that blocks loading until the "
           "decision and makes refusing as easy as agreeing.",
       method="Sucht im HTML nach Kennungen bekannter Consent-Anbieter (Usercentrics, Cookiebot, OneTrust, Borlabs, "
              "Complianz, CookieYes u. a.). Das ist eine Stichwortsuche und kann danebenliegen. Ob das Banner "
              "einen gleichwertigen Ablehnen-Button hat, wird nicht geprüft, dafür braucht es den Browser. ## "
              "Searches the HTML for identifiers of known consent providers (Usercentrics, Cookiebot, OneTrust, "
              "Borlabs, Complianz, CookieYes and others). This is a keyword search and can be wrong. Whether "
              "the banner has an equally prominent reject button is not checked, that needs a browser.",
       logic="Dienste eingebunden, aber keine Lösung erkannt: Warnung bei Tracking, sonst Hinweis. Lösung "
             "erkannt: Info. ## Services embedded but no solution detected: warning for tracking, otherwise "
             "note. Solution detected: info.",
       fix="Eine Einwilligungslösung einsetzen, die Skripte bis zur Zustimmung blockiert, und Ablehnen "
           "gleichwertig anbieten. ## Use a consent solution that blocks scripts until agreement and offers "
           "an equivalent reject option.",
       refs=[GDPR, EDPB_COOKIES], profiles="sd")
def consent_solution(snap):
    found = detect_cmp(snap)
    services = detect_services(snap)
    url = snap.pages[0].url if snap.pages else snap.target.url
    if found:
        names = ", ".join(found)
        return [F("PRV-CMP-001", S.INFO, url,
                  f"Einwilligungslösung erkannt: {names} (Ablehnen-Schaltfläche wird nicht geprüft)",
                  f"Consent solution detected: {names} (reject button is not checked)", names)]
    if services:
        tracking = any(category == "tracking" for category, _page in services.values())
        return [F("PRV-CMP-001", S.WARNING if tracking else S.NOTE, url,
                  "Externe Dienste eingebunden, aber keine Einwilligungslösung erkannt (Stichwortsuche)",
                  "Third-party services embedded but no consent solution detected (keyword search)",
                  ", ".join(sorted(services))[:120])]
    return []