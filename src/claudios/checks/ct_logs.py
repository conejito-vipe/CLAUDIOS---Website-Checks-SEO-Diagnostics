"""Zertifikats-Logs (Certificate Transparency) aus core/probe_ct.py. Läuft nur, wenn der Schalter 'crtsh' an ist."""
from __future__ import annotations

import re

from ..core.registry import check
from ._util import CheckSkipped, F, S

_INTERNAL = re.compile(r"(^|[.-])(admin|intranet|vpn|staging|stage|dev|test|git|gitlab|jenkins|backup|internal|"
                       r"vpn|sso|ldap|db|mysql|phpmyadmin)([.-]|\d|$)")


@check("SEC-CTL-001",
       title="Zertifikats-Logs (Certificate Transparency) ## Certificate logs (Certificate Transparency)",
       why="Jede öffentlich vertrauenswürdige Zertifizierungsstelle trägt ihre Zertifikate in öffentliche Logs ein. "
           "So zeigen sich Subdomains, die man vergessen hat oder die intern bleiben sollten, und Zertifikate, die "
           "jemand anderes für die Domain beantragt hat. ## Every publicly trusted certificate authority records its "
           "certificates in public logs. This reveals subdomains that were forgotten or should have stayed internal "
           "and certificates somebody else requested for the domain.",
       method="Nur mit eingeschaltetem Schalter auf der Seite Externe Dienste (Standard: aus). Eine Anfrage an crt.sh "
              "nach der registrierbaren Domain (über den Gatekeeper; der Dienst sieht die IP-Adresse des Nutzers). "
              "Ausgewertet werden Hostnamen mit internem Klang und Aussteller der Zertifikate der letzten 30 Tage. "
              "Antwortformat und Erreichbarkeit von crt.sh sind ungeprüft; der Dienst antwortet oft langsam. ## Only "
              "with the switch on the External services page turned on (default: off). One request to crt.sh for "
              "the registrable domain (through the gatekeeper; the service sees the user's IP address). Evaluates "
              "host names that sound internal and the issuers of the certificates of the last 30 days. The response "
              "format and availability of crt.sh are unverified; the service is often slow.",
       logic="Interner Hostname (admin, vpn, staging, git ...) in den Logs: Hinweis. Neue Zertifikate von mehr als "
             "einem Aussteller in 30 Tagen: Info (kann ein Wechsel sein oder ein fremd beantragtes Zertifikat). "
             "Dienst nicht erreichbar oder Antwort unlesbar: nicht ausgeführt. ## Internal host name (admin, vpn, "
             "staging, git ...) in the logs: note. New certificates from more than one issuer in 30 days: info (may "
             "be a change or a certificate requested by somebody else). Service unreachable or response unreadable: "
             "not executed.",
       fix="Interne Systeme nicht mit öffentlichen Zertifikaten und eigenen Namen betreiben (Wildcard oder interne "
           "Zertifizierungsstelle nutzen), mit CAA-Einträgen festlegen, wer ausstellen darf, und die Logs "
           "regelmäßig prüfen. ## Do not operate internal systems with public certificates and their own names (use a "
           "wildcard or an internal certificate authority), restrict who may issue with CAA records and review the "
           "logs regularly.",
       refs=["https://certificate.transparency.dev/", "https://www.rfc-editor.org/rfc/rfc9162"],
       profiles="sd", source="network")
def ct_logs(snap):
    data = snap.extra.get("ct")
    if data is None or not data.get("enabled"):
        raise CheckSkipped("ct_disabled")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    url = snap.target.url
    out = []
    internal = [h for h in data["hosts"] if _INTERNAL.search(h.removesuffix("." + snap.target.registrable))]
    if internal:
        out.append(F("SEC-CTL-001", S.NOTE, url, f"{len(internal)} Hostname(n) mit internem Namen in den Zertifikats-Logs: "
                     f"{', '.join(internal[:4])}", f"{len(internal)} host name(s) with an internal-sounding name in "
                     f"the certificate logs: {', '.join(internal[:4])}", ", ".join(internal[:10])))
    issuers = data.get("recent_issuers") or {}
    if len(issuers) > 1:
        names = ", ".join(sorted(issuers)[:4])
        out.append(F("SEC-CTL-001", S.INFO, url, f"Neue Zertifikate von {len(issuers)} Ausstellern in 30 Tagen: {names}",
                     f"New certificates from {len(issuers)} issuers in 30 days: {names}", names))
    return out
