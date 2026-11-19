"""Weitere Header- und Dateiprüfungen: Permissions-Policy, COOP/COEP/CORP und security.txt.
Header: reine Auswertung des Snapshots. security.txt: Daten aus der Probe core/probe_passive.py."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..core.registry import check
from ._util import CheckSkipped, F, S

MDN = "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/"
POWERFUL = ("camera", "microphone", "geolocation", "payment", "usb", "serial", "bluetooth", "display-capture")
_ISOLATION = (
    ("cross-origin-opener-policy", {"unsafe-none", "same-origin-allow-popups", "same-origin", "noopener-allow-popups"}),
    ("cross-origin-embedder-policy", {"unsafe-none", "require-corp", "credentialless"}),
    ("cross-origin-resource-policy", {"same-site", "same-origin", "cross-origin"}),
)


def _permissions(value: str) -> dict[str, list[str]]:
    """Grob nach der Syntax name=(...) oder name=*: Funktion -> Allowlist-Einträge."""
    out: dict[str, list[str]] = {}
    for part in value.split(",")[:60]:
        name, sep, rest = part.strip().partition("=")
        name = name.strip().lower()
        if name and sep:
            out[name] = rest.strip().strip("()").split()
    return out


@check("SEC-PPL-001",
       title="Permissions-Policy ## Permissions-Policy",
       why="Mit der Permissions-Policy legt eine Website fest, welche Browserfunktionen (Kamera, Mikrofon, Standort, "
           "Zahlung) sie und eingebettete Fremdinhalte nutzen dürfen. Ohne Richtlinie gelten die Standardrechte des "
           "Browsers auch für eingebettete Inhalte. ## With the Permissions-Policy a website decides which browser "
           "features (camera, microphone, location, payment) it and embedded third-party content may use. Without a "
           "policy the browser defaults also apply to embedded content.",
       method="Liest den Header Permissions-Policy (und den veralteten Feature-Policy) je Seite, zerlegt die Einträge "
              "und sucht Funktionen wie Kamera oder Mikrofon, die für alle Ursprünge (*) freigegeben sind. Jeder "
              "Befund erscheint einmal je Website. ## Reads the Permissions-Policy header (and the outdated "
              "Feature-Policy) per page, splits the entries and looks for features such as camera or microphone that "
              "are granted to all origins (*). Each finding appears once per website.",
       logic="Fehlt: Info. Nur der veraltete Header Feature-Policy: Info. Kamera, Mikrofon, Standort oder ähnliche "
             "Funktionen für alle Ursprünge freigegeben: Hinweis. ## Missing: info. Only the outdated Feature-Policy "
             "header: info. Camera, microphone, location or similar features granted to all origins: note.",
       fix="Header setzen, zum Beispiel Permissions-Policy: camera=(), microphone=(), geolocation=(). ## Set the "
           "header, for example Permissions-Policy: camera=(), microphone=(), geolocation=().",
       refs=[MDN + "Permissions-Policy", "https://www.w3.org/TR/permissions-policy/"])
def permissions_policy(snap):
    out, seen = [], set()
    for pg in snap.docs():
        value = pg.headers.get("permissions-policy", "").strip()
        if not value:
            kind = "legacy" if pg.headers.get("feature-policy") else "missing"
            if kind not in seen:
                seen.add(kind)
                if kind == "legacy":
                    out.append(F("SEC-PPL-001", S.INFO, pg.url,
                                 "Nur der veraltete Header Feature-Policy, keine Permissions-Policy",
                                 "Only the outdated Feature-Policy header, no Permissions-Policy"))
                else:
                    out.append(F("SEC-PPL-001", S.INFO, pg.url, "Keine Permissions-Policy",
                                 "No Permissions-Policy"))
            continue
        for name, tokens in _permissions(value).items():
            if name in POWERFUL and "*" in tokens and name not in seen:
                seen.add(name)
                out.append(F("SEC-PPL-001", S.NOTE, pg.url, f"Permissions-Policy gibt {name} für alle Ursprünge frei",
                             f"Permissions-Policy grants {name} to all origins", value[:80]))
    return out


@check("SEC-COI-001",
       title="Cross-Origin-Richtlinien (COOP, COEP, CORP) ## Cross-origin policies (COOP, COEP, CORP)",
       why="Diese drei Header trennen die Seite von fremden Fenstern und Ressourcen. Sie schützen vor "
           "Seitenkanal-Angriffen wie Spectre und sind Voraussetzung für die Cross-Origin-Isolation. Ungültige "
           "Werte werden vom Browser ignoriert. ## These three headers separate the page from foreign windows and "
           "resources. They protect against side-channel attacks such as Spectre and are required for "
           "cross-origin isolation. Invalid values are ignored by the browser.",
       method="Liest Cross-Origin-Opener-Policy, Cross-Origin-Embedder-Policy und Cross-Origin-Resource-Policy je "
              "Seite und vergleicht die Werte mit den erlaubten. ## Reads Cross-Origin-Opener-Policy, "
              "Cross-Origin-Embedder-Policy and Cross-Origin-Resource-Policy per page and compares the values with "
              "the allowed ones.",
       logic="Ungültiger Wert: Hinweis. Keiner der drei gesetzt: Info. COEP ohne COOP same-origin: Info. ## "
             "Invalid value: note. None of the three set: info. COEP without COOP same-origin: info.",
       fix="Zum Beispiel Cross-Origin-Opener-Policy: same-origin und Cross-Origin-Resource-Policy: same-site senden; "
           "COEP nur setzen, wenn alle Fremdressourcen es erlauben. ## For example send "
           "Cross-Origin-Opener-Policy: same-origin and Cross-Origin-Resource-Policy: same-site; set COEP only if "
           "all third-party resources allow it.",
       refs=[MDN + "Cross-Origin-Opener-Policy", MDN + "Cross-Origin-Embedder-Policy",
             MDN + "Cross-Origin-Resource-Policy"])
def isolation(snap):
    out, seen, values = [], set(), {}
    docs = snap.docs()
    for pg in docs:
        for header, valid in _ISOLATION:
            value = pg.headers.get(header, "").split(";")[0].strip().lower()
            if not value:
                continue
            values.setdefault(header, value)
            if value not in valid and (header, value) not in seen:
                seen.add((header, value))
                name = header.title()
                out.append(F("SEC-COI-001", S.NOTE, pg.url, f"{name}: ungültiger Wert",
                             f"{name}: invalid value", value[:60]))
    if docs and not values:
        out.append(F("SEC-COI-001", S.INFO, snap.target.url,
                     "Weder Cross-Origin-Opener-, -Embedder- noch -Resource-Policy gesetzt",
                     "Neither Cross-Origin-Opener-, -Embedder- nor -Resource-Policy set"))
    coep = values.get("cross-origin-embedder-policy")
    if coep in ("require-corp", "credentialless") and values.get("cross-origin-opener-policy") != "same-origin":
        out.append(F("SEC-COI-001", S.INFO, snap.target.url,
                     "COEP ist gesetzt, aber COOP nicht auf same-origin: keine Cross-Origin-Isolation",
                     "COEP is set but COOP is not same-origin: no cross-origin isolation"))
    return out


def _fields(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for raw in text.splitlines()[:200]:
        line = raw.strip()
        if not line or line.startswith(("#", "-----")):
            continue
        key, sep, value = line.partition(":")
        if sep:
            out.setdefault(key.strip().lower(), []).append(value.strip())
    return out


def _expires(value: str) -> datetime | None:
    try:
        when = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


@check("SEC-TXT-001",
       title="security.txt (Meldeweg für Sicherheitslücken) ## security.txt (reporting channel for vulnerabilities)",
       why="Die Datei security.txt sagt Sicherheitsforschern, wohin sie eine gefundene Lücke melden können. Fehlt sie, "
           "bleiben Meldungen oft aus oder landen öffentlich. ## The security.txt file tells security researchers "
           "where to report a vulnerability. Without it reports often stay away or end up public.",
       method="Ruft /.well-known/security.txt ab (bei 404 zusätzlich /security.txt) und prüft nach RFC 9116 die "
              "Pflichtfelder Contact und Expires, das Datumsformat, den Ablauf und den Inhaltstyp. ## Fetches "
              "/.well-known/security.txt (on 404 also /security.txt) and checks per RFC 9116 the required fields "
              "Contact and Expires, the date format, the expiry and the content type.",
       logic="Fehlt: Info. Nur am alten Ort, abgelaufen, ohne Contact oder Expires, HTML statt Text: Warnung bis "
             "Hinweis. ## Missing: info. Only at the old location, expired, without Contact or Expires, HTML "
             "instead of text: warning to note.",
       fix="Datei unter /.well-known/security.txt mit Contact: mailto:... und Expires: (ISO 8601, unter einem Jahr) "
           "anlegen. ## Create the file at /.well-known/security.txt with Contact: mailto:... and Expires: (ISO 8601, "
           "under one year).",
       refs=["https://www.rfc-editor.org/rfc/rfc9116", "https://securitytxt.org/"],
       profiles="sd", source="network")
def security_txt(snap):
    data = snap.extra.get("passive")
    if data is None:
        raise CheckSkipped("no_passive_data")
    rec = data.get("security_txt")
    if not isinstance(rec, dict) or rec.get("error"):
        raise CheckSkipped("security_txt_unreachable")
    url, status = snap.target.url, rec.get("status")
    if status in (404, 410):
        legacy = rec.get("legacy")
        if isinstance(legacy, dict) and legacy.get("status") == 200:
            return [F("SEC-TXT-001", S.NOTE, url,
                      "security.txt liegt nur am alten Ort /security.txt (richtig: /.well-known/security.txt)",
                      "security.txt exists only at the old location /security.txt (correct: /.well-known/security.txt)")]
        return [F("SEC-TXT-001", S.INFO, url, "Keine security.txt gefunden", "No security.txt found")]
    if status != 200:
        return [F("SEC-TXT-001", S.INFO, url, f"security.txt antwortet mit HTTP {status}",
                  f"security.txt answers with HTTP {status}")]
    text, ctype = str(rec.get("text", "")), str(rec.get("content_type", ""))
    if "html" in ctype or text.lstrip().lower().startswith(("<!doctype", "<html")):
        return [F("SEC-TXT-001", S.WARNING, url, "security.txt liefert HTML statt Text (vermutlich eine Fehlerseite)",
                  "security.txt returns HTML instead of text (probably an error page)")]
    out = []
    if ctype and not ctype.startswith("text/plain"):
        out.append(F("SEC-TXT-001", S.NOTE, url, "security.txt hat nicht den Inhaltstyp text/plain",
                     "security.txt does not have the content type text/plain", ctype[:60]))
    fields = _fields(text)
    contacts = fields.get("contact", [])
    if not contacts:
        out.append(F("SEC-TXT-001", S.WARNING, url, "security.txt ohne Contact (Pflichtfeld)",
                     "security.txt without Contact (required field)"))
    else:
        bad = [c for c in contacts if not c.lower().startswith(("mailto:", "tel:", "https:"))]
        if bad:
            out.append(F("SEC-TXT-001", S.NOTE, url, "Contact in security.txt nutzt kein mailto:, tel: oder https:",
                         "Contact in security.txt uses no mailto:, tel: or https:", bad[0].split(":")[0][:20]))
    expires = fields.get("expires", [])
    if not expires:
        out.append(F("SEC-TXT-001", S.WARNING, url, "security.txt ohne Expires (Pflichtfeld)",
                     "security.txt without Expires (required field)"))
    else:
        when = _expires(expires[0])
        now = datetime.now(UTC)
        if when is None:
            out.append(F("SEC-TXT-001", S.WARNING, url, "Expires in security.txt hat kein gültiges Datumsformat",
                         "Expires in security.txt has no valid date format", expires[0][:40]))
        elif when < now:
            out.append(F("SEC-TXT-001", S.WARNING, url, "security.txt ist abgelaufen (Expires liegt in der Vergangenheit)",
                         "security.txt has expired (Expires is in the past)", expires[0][:40]))
        elif when > now + timedelta(days=366):
            out.append(F("SEC-TXT-001", S.NOTE, url, "Expires in security.txt liegt mehr als ein Jahr in der Zukunft",
                         "Expires in security.txt is more than a year in the future", expires[0][:40]))
    return out
