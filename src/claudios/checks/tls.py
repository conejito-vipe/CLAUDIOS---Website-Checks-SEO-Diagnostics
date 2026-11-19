"""TLS-Zertifikat aus der Probe 'tls' (ein Handshake). Alte Protokolle und Cipher folgen mit sslyze."""
from __future__ import annotations

from ..core.registry import check
from ._util import CheckSkipped, F, S


@check("TLS-CRT-001",
       title="TLS-Zertifikat (Restlaufzeit, Protokoll) ## TLS certificate (remaining validity, protocol)",
       why="Ein abgelaufenes Zertifikat lässt Browser eine Warnseite zeigen, und die Seite ist praktisch nicht mehr "
           "erreichbar. Ein Server, der nur TLS 1.2 anbietet, verzichtet auf das schnellere und sicherere TLS 1.3. ## "
           "An expired certificate makes browsers show a warning page and the site is practically unreachable. "
           "A server that only offers TLS 1.2 forgoes the faster and more secure TLS 1.3.",
       method="Ein einziger TLS-Handshake zur zuvor als öffentlich geprüften IP (mindestens TLS 1.2, "
              "Zertifikatsprüfung aktiv, keine Anwendungsdaten). Ausgewertet werden Restlaufzeit und ausgehandelte "
              "Version. Alte Protokolle (TLS 1.0/1.1) und Cipher werden hier nicht geprüft. ## A single TLS "
              "handshake to the IP previously verified as public (at least TLS 1.2, certificate validation "
              "active, no application data). Remaining validity and negotiated version are evaluated. Old "
              "protocols (TLS 1.0/1.1) and ciphers are not checked here.",
       logic="Unter 14 Tagen Restlaufzeit: Fehler. Unter 30 Tagen: Warnung. Nur TLS 1.2 ausgehandelt: Info. ## "
             "Below 14 days remaining: error. Below 30 days: warning. Only TLS 1.2 negotiated: info.",
       fix="Automatische Erneuerung einrichten (zum Beispiel ACME/Let's Encrypt) und TLS 1.3 aktivieren. ## Set up "
           "automatic renewal (for example ACME/Let's Encrypt) and enable TLS 1.3.",
       refs=["https://www.rfc-editor.org/rfc/rfc8446", "https://www.rfc-editor.org/rfc/rfc5280"],
       profiles="sd", source="network")
def certificate(snap):
    data = snap.extra.get("tls")
    if data is None:
        raise CheckSkipped("no_tls_data")
    if data.get("error"):
        raise CheckSkipped("tls_probe_failed")
    url, days, out = snap.target.url, data["days_left"], []
    if days < 14:
        out.append(F("TLS-CRT-001", S.ERROR, url, f"Das Zertifikat läuft in {days} Tagen ab (oder ist abgelaufen)",
                     f"The certificate expires in {days} days (or has expired)", data.get("issuer", "")))
    elif days < 30:
        out.append(F("TLS-CRT-001", S.WARNING, url, f"Das Zertifikat läuft in {days} Tagen ab",
                     f"The certificate expires in {days} days", data.get("issuer", "")))
    if data.get("version") == "TLSv1.2":
        out.append(F("TLS-CRT-001", S.INFO, url, "Der Server hat nur TLS 1.2 ausgehandelt (TLS 1.3 nicht genutzt)",
                     "The server negotiated only TLS 1.2 (TLS 1.3 not used)"))
    return out