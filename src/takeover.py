"""Subdomain-Takeover-Hinweise. Die Daten stammen aus der Probe-Phase (nur lesende DNS-Abfragen)."""
from __future__ import annotations

from ..core.registry import check
from ._util import CheckSkipped, F, S

OWASP_TAKEOVER = ("https://owasp.org/www-project-web-security-testing-guide/latest/"
                  "4-Web_Application_Security_Testing/02-Configuration_and_Deployment_Management_Testing/"
                  "10-Test_for_Subdomain_Takeover")


@check("TKO-DNS-001",
       title="Subdomain-Takeover (hängende CNAME-Einträge) ## Subdomain takeover (dangling CNAME records)",
       why="Zeigt eine Subdomain per CNAME auf einen Dienst, bei dem das Konto oder die Ressource nicht mehr "
           "existiert, kann ein Angreifer dort dasselbe Ziel neu anlegen und unter Ihrer Domain Inhalte oder "
           "Phishing-Seiten ausliefern. ## If a subdomain points via CNAME to a service where the account or "
           "resource no longer exists, an attacker can register that target again and serve content or phishing "
           "pages under your domain.",
       method="Sammelt Subdomains der geprüften Domain, die auf den gecrawlten Seiten vorkommen (Links, Skripte, "
              "Bilder, iFrames), höchstens 20. Fragt deren CNAME-Kette über DNS-over-HTTPS ab und prüft, ob das "
              "Ziel noch eine A- oder AAAA-Adresse hat. Subdomains werden nie erraten (kein Brute-Force). "
              "HTTP-Fingerprints von Diensten (zum Beispiel GitHub Pages) werden noch nicht geprüft. ## Collects "
              "subdomains of the checked domain that appear on the crawled pages (links, scripts, images, "
              "iframes), at most 20. Queries their CNAME chain via DNS-over-HTTPS and checks whether the target "
              "still has an A or AAAA address. Subdomains are never guessed (no brute force). HTTP fingerprints "
              "of services (for example GitHub Pages) are not checked yet.",
       logic="CNAME-Ziel ohne Adresse bei einem bekannten Dienst: Fehler. Bei unbekanntem Ziel: Warnung. "
             "Abfragelimit erreicht: Info. ## CNAME target without address at a known service: error. At an "
             "unknown target: warning. Query limit reached: info.",
       fix="Den DNS-Eintrag löschen oder die Ressource beim Dienst neu anlegen, bevor es jemand anderes tut. ## "
           "Delete the DNS record or re-create the resource at the service before somebody else does.",
       refs=[OWASP_TAKEOVER, "https://github.com/EdOverflow/can-i-take-over-xyz"], profiles="sd",
       source="network")
def takeover(snap):
    data = snap.extra.get("takeover")
    if data is None:
        raise CheckSkipped("no_takeover_data")
    out = []
    url = snap.target.url
    for rec in data["records"]:
        if rec["resolves"] is not False:
            continue
        evidence = f"{rec['host']} → {rec['target']}"
        if rec["service"]:
            out.append(F("TKO-DNS-001", S.ERROR, url,
                         f"Subdomain {rec['host']} zeigt auf {rec['service']}, das Ziel existiert nicht (Takeover-Risiko)",
                         f"Subdomain {rec['host']} points to {rec['service']}, the target does not exist (takeover risk)",
                         evidence))
        else:
            out.append(F("TKO-DNS-001", S.WARNING, url,
                         f"Hängender CNAME bei {rec['host']}: das Ziel löst nicht auf",
                         f"Dangling CNAME at {rec['host']}: the target does not resolve", evidence))
    if data["limited"]:
        out.append(F("TKO-DNS-001", S.INFO, url, "Takeover-Prüfung wegen des Abfragelimits nicht vollständig",
                     "Takeover check incomplete because of the query limit"))
    return out