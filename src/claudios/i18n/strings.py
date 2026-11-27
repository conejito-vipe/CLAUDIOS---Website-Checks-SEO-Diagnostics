"""UI-Texte DE/EN. Keine festen Texte im UI-Code. Beide Sprachen müssen identische Schlüssel haben (Test).
Weitere Texte kommen als neue Datei i18n/strings_*.py. Die Schreibweise im Programm ist CLAUDIOS."""
from __future__ import annotations

from ..core.numfmt import format_number

_lang = "de"


def set_lang(lang: str) -> None:
    global _lang
    if lang not in TEXTS:
        raise ValueError("unsupported language")
    _lang = lang


def get_lang() -> str:
    return _lang


def text(lang: str, key: str, **kw: object) -> str:
    value = TEXTS[lang][key]
    return value.format_map(kw) if kw else value


def t(key: str, **kw: object) -> str:
    return text(_lang, key, **kw)


def n(value: float, decimals: int = 0) -> str:
    """Zahlen immer mit der Formatierung der gewählten Sprache (DE 1.000 / EN 1,000)."""
    return format_number(value, _lang, decimals)


TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "app.title": "CLAUDIOS – Website Checks, SEO & Diagnostics",
        "nav.scan": "Scan", "nav.results": "Ergebnisse", "nav.handbook": "Handbuch",
        "nav.tech": "Technik-Doku", "nav.settings": "Einstellungen", "nav.about": "Info",
        "scan.url": "Adresse der Website", "scan.url_ph": "beispiel.de", "scan.profile": "Profil",
        "profile.quick": "Schnell", "profile.standard": "Standard", "profile.deep": "Tief",
        "scan.confirm": "Ich bin berechtigt, diese Domain zu testen",
        "scan.level": "Stufe 1 (Selbstauskunft): höchstens {pages} Seiten und {depth} Ebenen. "
                      "Aktive Prüfungen und die Search Console gibt es erst mit Stufe 2.",
        "scan.google": "Mit Google verifizieren (Stufe 2) …",
        "scan.start": "Scan starten", "scan.cancel": "Abbrechen",
        "scan.idle": "Bereit.", "scan.running": "Scan läuft …",
        "scan.progress": "Seite {cur} von höchstens {total}",
        "scan.probe": "Zusatzprüfung {cur} von {total}: {name}",
        "probe.dns": "DNS und E-Mail-Sicherheit", "probe.takeover": "Subdomain-Prüfung",
        "probe.ads": "ads.txt", "probe.sitemap": "Sitemap", "probe.soft404": "Fehlerseiten-Test",
        "probe.links": "Externe Links",
        "scan.done": "Scan beendet: {status}.", "scan.cancelling": "Abbruch angefordert …",
        "status.complete": "vollständig", "status.limited": "mit Einschränkungen", "status.aborted": "abgebrochen",
        "res.empty": "Noch kein Ergebnis. Starte einen Scan.",
        "res.summary": "{target} · Status: {status} · Gesamtwertung {score}/100 · {pages} Seiten · "
                       "{requests} Anfragen · {size}",
        "res.notrun": "{count} Prüfungen wurden nicht ausgeführt (das zählt nie als bestanden).",
        "res.col.sev": "Schwere", "res.col.check": "Prüfung", "res.col.count": "Anzahl", "res.col.finding": "Befund",
        "res.export": "Als ZIP für Claude exportieren …",
        "export.title": "Export-Vorschau",
        "export.text": "Diese Dateien kommen in die ZIP (Passwörter, Cookie-Werte und Tokens sind nie enthalten):"
                       "\n\n{files}\n\nPrüfe die ZIP trotzdem vor dem Hochladen. Exportieren?",
        "export.saved": "Gespeichert: {path}", "export.dialog": "ZIP speichern",
        "sev.0": "Info", "sev.1": "Hinweis", "sev.2": "Warnung", "sev.3": "Fehler", "sev.4": "Kritisch",
        "settings.localhost": "Localhost-Scans erlauben (nur für eigene Entwicklung)",
        "settings.localhost_warn": "Achtung: Lokale Ziele werden nicht verifiziert und laufen ohne HTTPS-Pflicht.",
        "settings.limits": "Die Grenzen ({depth} Ebenen, {p1} bzw. {p2} Seiten, Drosselung) sind fest im "
                           "Programm und nicht einstellbar.",
        "doc.search": "Suchen …",
        "doc.intro": "CLAUDIOS prüft eine Website auf sauberes HTML, CSS und JavaScript (W3C-Referenzen), "
                     "Sicherheit, Datenschutz und SEO. Die Prüfungen sind passiv (normale Seitenaufrufe), "
                     "gedrosselt und auf {depth} Ebenen begrenzt. Ergebnisse sind technische Indizien, keine "
                     "Rechtsberatung. Nur für eigene oder ausdrücklich freigegebene Websites. Zu jeder Prüfung "
                     "steht unten, warum sie wichtig ist.",
        "doc.tech_intro": "Technische Dokumentation, automatisch aus der Check-Registry erzeugt.",
        "doc.why": "Warum?", "doc.fix": "Behebung", "doc.refs": "Referenzen", "doc.method": "Methode",
        "doc.logic": "Bewertung", "doc.kind": "Art", "doc.profiles": "Prüfprofile", "doc.passive": "passiv",
        "doc.active": "aktiv", "doc.code": "Code", "doc.none": "Keine Treffer.",
        "about.title": "Über CLAUDIOS",
        "about.text": "CLAUDIOS {version}\nWebsite Checks, SEO & Diagnostics\n\n"
                      "Freeware · vibecoded with Claude (Anthropic) by conejito-vipe with love ♥\n"
                      "{lines} Zeilen Python\n\n"
                      "Keine Gewährleistung und Haftung, soweit gesetzlich zulässig.\n"
                      "Nur für eigene oder ausdrücklich freigegebene Websites. Ergebnisse sind technische "
                      "Indizien, keine Rechtsberatung.\n\nProjekt: {repo}",
        "about.licenses": "Code: © conejito-vipe, quelloffene Lizenz mit Einschränkungen: keine kommerzielle "
                          "Nutzung, keine Veränderung, keine Weitergabe (siehe LICENSE.de.txt).\n"
                          "Logo: © conejito-vipe, mit KI-Unterstützung erstellt, Nutzung nur zusammen mit "
                          "CLAUDIOS.\nBibliotheken von Dritten behalten ihre eigenen Lizenzen: httpx (BSD-3), "
                          "Beautiful Soup (MIT), dnspython (ISC), publicsuffix2 (MIT/MPL-2.0), PySide6 (LGPL-3.0), "
                          "openpyxl (MIT).\nQuellen und Details: THIRD_PARTY_NOTICES.de.md und assets/ASSETS.de.md "
                          "im Repository.",
        "about.close": "Schließen",
        "footer.before": "vibecoded with Claude (Anthropic) by conejito-vipe with love",
        "footer.after": "· {lines} Zeilen Python",
        "err.todo": "Was du tun kannst:",
        "splash.s1": "Prüfe Arbeitsordner …", "splash.s2": "Lade Fehlerkatalog …",
        "splash.s3": "Prüfe Prüfregister …", "splash.s4": "Lade Vergleichsdaten (Public Suffix List) …",
        "splash.s5": "Prüfe Audit-Protokoll …", "splash.ready": "Bereit",
        "splash.audit_warn": "Das Audit-Protokoll wurde verändert oder ist beschädigt (Hash-Kette ungültig).",
    },
    "en": {
        "app.title": "CLAUDIOS – Website Checks, SEO & Diagnostics",
        "nav.scan": "Scan", "nav.results": "Results", "nav.handbook": "Manual",
        "nav.tech": "Technical docs", "nav.settings": "Settings", "nav.about": "About",
        "scan.url": "Website address", "scan.url_ph": "example.com", "scan.profile": "Profile",
        "profile.quick": "Quick", "profile.standard": "Standard", "profile.deep": "Deep",
        "scan.confirm": "I am authorised to test this domain",
        "scan.level": "Level 1 (self-declaration): at most {pages} pages and {depth} levels. "
                      "Active checks and Search Console are only available with level 2.",
        "scan.google": "Verify with Google (level 2) …",
        "scan.start": "Start scan", "scan.cancel": "Cancel",
        "scan.idle": "Ready.", "scan.running": "Scan running …",
        "scan.progress": "Page {cur} of at most {total}",
        "scan.probe": "Extra check {cur} of {total}: {name}",
        "probe.dns": "DNS and e-mail security", "probe.takeover": "Subdomain check",
        "probe.ads": "ads.txt", "probe.sitemap": "Sitemap", "probe.soft404": "Error-page test",
        "probe.links": "External links",
        "scan.done": "Scan finished: {status}.", "scan.cancelling": "Cancel requested …",
        "status.complete": "complete", "status.limited": "with limitations", "status.aborted": "aborted",
        "res.empty": "No result yet. Start a scan.",
        "res.summary": "{target} · Status: {status} · Overall score {score}/100 · {pages} pages · "
                       "{requests} requests · {size}",
        "res.notrun": "{count} checks were not executed (this never counts as passed).",
        "res.col.sev": "Severity", "res.col.check": "Check", "res.col.count": "Count", "res.col.finding": "Finding",
        "res.export": "Export ZIP for Claude …",
        "export.title": "Export preview",
        "export.text": "These files go into the ZIP (passwords, cookie values and tokens are never included):"
                       "\n\n{files}\n\nPlease still check the ZIP before uploading. Export?",
        "export.saved": "Saved: {path}", "export.dialog": "Save ZIP",
        "sev.0": "Info", "sev.1": "Note", "sev.2": "Warning", "sev.3": "Error", "sev.4": "Critical",
        "settings.localhost": "Allow localhost scans (own development only)",
        "settings.localhost_warn": "Warning: local targets are not verified and are exempt from the HTTPS rule.",
        "settings.limits": "The limits ({depth} levels, {p1} or {p2} pages, throttling) are built into the "
                           "program and cannot be changed.",
        "doc.search": "Search …",
        "doc.intro": "CLAUDIOS checks a website for clean HTML, CSS and JavaScript (W3C references), "
                     "security, privacy and SEO. The checks are passive (normal page requests), throttled and "
                     "limited to {depth} levels. Results are technical indications, not legal advice. Only for "
                     "your own or explicitly authorised websites. Below, every check explains why it matters.",
        "doc.tech_intro": "Technical documentation, generated automatically from the check registry.",
        "doc.why": "Why?", "doc.fix": "Fix", "doc.refs": "References", "doc.method": "Method",
        "doc.logic": "Rating", "doc.kind": "Type", "doc.profiles": "Profiles", "doc.passive": "passive",
        "doc.active": "active", "doc.code": "Code", "doc.none": "No matches.",
        "about.title": "About CLAUDIOS",
        "about.text": "CLAUDIOS {version}\nWebsite Checks, SEO & Diagnostics\n\n"
                      "Freeware · vibecoded with Claude (Anthropic) by conejito-vipe with love ♥\n"
                      "{lines} lines of Python\n\n"
                      "No warranty and no liability, as far as legally permitted.\n"
                      "Only for your own or explicitly authorised websites. Results are technical "
                      "indications, not legal advice.\n\nProject: {repo}",
        "about.licenses": "Code: © conejito-vipe, source-available licence with restrictions: no commercial use, "
                          "no modification, no distribution (see LICENSE).\n"
                          "Logo: © conejito-vipe, created with AI assistance, use only together with CLAUDIOS.\n"
                          "Third-party libraries keep their own licences: httpx (BSD-3), Beautiful Soup (MIT), "
                          "dnspython (ISC), publicsuffix2 (MIT/MPL-2.0), PySide6 (LGPL-3.0), openpyxl (MIT).\n"
                          "Sources and details: THIRD_PARTY_NOTICES.md and assets/ASSETS.md in the repository.",
        "about.close": "Close",
        "footer.before": "vibecoded with Claude (Anthropic) by conejito-vipe with love",
        "footer.after": "· {lines} lines of Python",
        "err.todo": "What you can do:",
        "splash.s1": "Checking working folder …", "splash.s2": "Loading error catalog …",
        "splash.s3": "Checking check registry …", "splash.s4": "Loading comparison data (Public Suffix List) …",
        "splash.s5": "Checking audit log …", "splash.ready": "Ready",
        "splash.audit_warn": "The audit log was modified or is damaged (hash chain invalid).",
    },
}
