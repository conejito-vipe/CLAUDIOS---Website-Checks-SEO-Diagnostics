"""Domainablauf aus der RDAP-Abfrage (core/probe_rdap.py). Läuft nur, wenn der Schalter 'rdap' an ist."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from ..core.registry import check
from ._util import CheckSkipped, F, S

_DANGER = {"pendingdelete", "redemptionperiod"}
_HOLD = {"clienthold", "serverhold"}


def _when(value) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


@check("SEC-DOM-001",
       title="Domainablauf (RDAP) ## Domain expiry (RDAP)",
       why="Läuft eine Domain ab, verschwinden Website und E-Mail. Danach kann sie jemand anderes registrieren und "
           "unter dem alten Namen Inhalte ausliefern oder Mails empfangen. ## When a domain expires, website and "
           "e-mail disappear. Afterwards somebody else can register it and serve content or receive mail under the "
           "old name.",
       method="Nur mit eingeschaltetem Schalter auf der Seite Externe Dienste (Standard: aus). Fragt die Liste der "
              "RDAP-Server bei IANA und danach den zuständigen Server nach der registrierbaren Domain ab (zwei "
              "Anfragen über den Gatekeeper). Ausgewertet werden das Ablaufdatum und Status wie pending delete. Der "
              "Server sieht die IP-Adresse des Nutzers. Format und Status-Texte stammen aus dem Gedächtnis und sind "
              "ungeprüft; nicht jede Endung bietet RDAP an. ## Only with the switch on the External services page "
              "turned on (default: off). Queries the list of RDAP servers at IANA and then the responsible server for "
              "the registrable domain (two requests through the gatekeeper). Evaluates the expiry date and statuses "
              "such as pending delete. The server sees the user's IP address. Format and status texts come from "
              "memory and are unverified; not every TLD offers RDAP.",
       logic="Abgelaufen oder unter 14 Tagen, pending delete, redemption period: Fehler. Unter 30 Tagen, hold: "
             "Warnung. Unter 60 Tagen: Hinweis. Kein Ablaufdatum in der Antwort: Info. ## Expired or below 14 days, "
             "pending delete, redemption period: error. Below 30 days, hold: warning. Below 60 days: note. No expiry "
             "date in the response: info.",
       fix="Domain beim Registrar verlängern und die automatische Verlängerung einschalten. ## Renew the domain at the "
           "registrar and turn on automatic renewal.",
       refs=["https://www.rfc-editor.org/rfc/rfc9083", "https://www.rfc-editor.org/rfc/rfc9224"],
       profiles="sd", source="network")
def domain_expiry(snap):
    data = snap.extra.get("rdap")
    if data is None:
        raise CheckSkipped("no_rdap_data")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    url, domain, out = snap.target.url, snap.target.registrable, []
    when = _when(data.get("expires"))
    if when is None:
        out.append(F("SEC-DOM-001", S.INFO, url, "Die RDAP-Antwort enthält kein Ablaufdatum",
                     "The RDAP response contains no expiry date"))
    else:
        days, date = (when - datetime.now(UTC)).days, when.date().isoformat()
        if days < 0:
            out.append(F("SEC-DOM-001", S.ERROR, url, f"Die Domain {domain} ist abgelaufen",
                         f"The domain {domain} has expired", date))
        elif days < 14:
            out.append(F("SEC-DOM-001", S.ERROR, url, f"Die Domain {domain} läuft in {days} Tagen ab",
                         f"The domain {domain} expires in {days} days", date))
        elif days < 30:
            out.append(F("SEC-DOM-001", S.WARNING, url, f"Die Domain {domain} läuft in {days} Tagen ab",
                         f"The domain {domain} expires in {days} days", date))
        elif days < 60:
            out.append(F("SEC-DOM-001", S.NOTE, url, f"Die Domain {domain} läuft in {days} Tagen ab",
                         f"The domain {domain} expires in {days} days", date))
    for status in data.get("statuses") or []:
        key = re.sub(r"[\s_-]", "", str(status).lower())
        if key in _DANGER:
            out.append(F("SEC-DOM-001", S.ERROR, url, f"Die Domain hat den Status {status} (Löschung droht)",
                         f"The domain has the status {status} (deletion looms)", str(status)))
        elif key in _HOLD:
            out.append(F("SEC-DOM-001", S.WARNING, url, f"Die Domain hat den Status {status} (sie löst nicht auf)",
                         f"The domain has the status {status} (it does not resolve)", str(status)))
    return out
