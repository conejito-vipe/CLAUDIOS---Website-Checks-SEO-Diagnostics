"""Prüfungen mit Daten aus der Probe core/probe_passive.py: MTA-STS-Richtliniendatei und Fehlerseiten von Subdomains,
die auf Fremddienste zeigen."""
from __future__ import annotations

from ..core.dnsprobe import txt_join
from ..core.registry import check
from ._util import CheckSkipped, F, S

RFC = "https://www.rfc-editor.org/rfc/"


def _policy(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for raw in text.splitlines()[:200]:
        key, sep, value = raw.strip().partition(":")
        if sep:
            out.setdefault(key.strip().lower(), []).append(value.strip())
    return out


def _mx_hosts(records: dict) -> list[str]:
    hosts = []
    for item in records.get("mx") or []:
        parts = str(item).split()
        if len(parts) >= 2 and parts[-1] != ".":
            hosts.append(parts[-1].rstrip(".").lower())
    return hosts


def _matches(host: str, pattern: str) -> bool:
    pattern = pattern.strip().lower().rstrip(".")
    if pattern.startswith("*."):
        return host.endswith(pattern[1:])
    return host == pattern


@check("DNS-MTF-001",
       title="MTA-STS-Richtliniendatei ## MTA-STS policy file",
       why="Ein MTA-STS-Eintrag im DNS wirkt nur mit der passenden Richtliniendatei. Fehlt sie oder ist sie "
           "fehlerhaft, ignorieren Absender den Schutz oder liefern im enforce-Modus nicht mehr zu. ## An MTA-STS "
           "record in DNS only works with the matching policy file. If it is missing or faulty, senders ignore the "
           "protection or stop delivering in enforce mode.",
       method="Nur wenn ein TXT-Eintrag _mta-sts mit v=STSv1 existiert: ruft https://mta-sts.<domain>/.well-known/"
              "mta-sts.txt ohne Weiterleitung ab und prüft version, mode, mx, max_age, den Inhaltstyp und ob jeder "
              "MX-Host der Domain zu einem mx-Muster passt. ## Only if a TXT record _mta-sts with v=STSv1 exists: "
              "fetches https://mta-sts.<domain>/.well-known/mta-sts.txt without redirect and checks version, mode, "
              "mx, max_age, the content type and whether every MX host of the domain matches an mx pattern.",
       logic="Datei fehlt, ungültig oder MX-Host nicht abgedeckt: Warnung. Modus testing oder none, max_age unter "
             "einem Tag: Hinweis. max_age unter einer Woche: Info. ## File missing, invalid or MX host not "
             "covered: warning. Mode testing or none, max_age below one day: note. max_age below one week: info.",
       fix="Datei mit version: STSv1, mode: enforce, allen mx-Hosts und max_age: 604800 oder mehr bereitstellen. ## "
           "Provide a file with version: STSv1, mode: enforce, all mx hosts and max_age: 604800 or more.",
       refs=[RFC + "rfc8461"], profiles="sd", source="network")
def mta_sts_file(snap):
    passive, dns = snap.extra.get("passive"), snap.extra.get("dns")
    if passive is None:
        raise CheckSkipped("no_passive_data")
    if dns is None:
        raise CheckSkipped("no_dns_data")
    records = dns.get("records") or {}
    txts = records.get("mta_sts")
    if txts is None:
        raise CheckSkipped("dns_mta_unavailable")
    if not any(txt_join(x).lower().startswith("v=stsv1") for x in txts):
        return []  # kein MTA-STS-Eintrag: das meldet DNS-MTA-001
    rec = passive.get("mta_sts")
    if not isinstance(rec, dict):
        raise CheckSkipped("mta_sts_not_fetched")
    if rec.get("error"):
        raise CheckSkipped("mta_sts_unreachable")
    url, status = snap.target.url, rec.get("status")
    if status != 200:
        return [F("DNS-MTF-001", S.WARNING, url,
                  f"MTA-STS-Eintrag vorhanden, aber die Richtliniendatei liefert HTTP {status} (Weiterleitungen sind nicht erlaubt)",
                  f"MTA-STS record present but the policy file returns HTTP {status} (redirects are not allowed)")]
    out = []
    ctype = str(rec.get("content_type", ""))
    if ctype and not ctype.startswith("text/plain"):
        out.append(F("DNS-MTF-001", S.NOTE, url, "Die MTA-STS-Richtlinie hat nicht den Inhaltstyp text/plain",
                     "The MTA-STS policy does not have the content type text/plain", ctype[:60]))
    fields = _policy(str(rec.get("text", "")))
    if (fields.get("version") or [""])[0].lower() != "stsv1":
        out.append(F("DNS-MTF-001", S.WARNING, url, "MTA-STS-Richtlinie ohne gültige version: STSv1",
                     "MTA-STS policy without a valid version: STSv1"))
    mode = (fields.get("mode") or [""])[0].lower()
    if mode not in ("enforce", "testing", "none"):
        out.append(F("DNS-MTF-001", S.WARNING, url, "MTA-STS-Richtlinie ohne gültigen mode",
                     "MTA-STS policy without a valid mode", mode[:20]))
    elif mode != "enforce":
        out.append(F("DNS-MTF-001", S.NOTE, url, f"MTA-STS läuft im Modus {mode} und erzwingt nichts",
                     f"MTA-STS runs in mode {mode} and enforces nothing"))
    patterns = fields.get("mx", [])
    if not patterns:
        out.append(F("DNS-MTF-001", S.WARNING, url, "MTA-STS-Richtlinie ohne mx-Zeile",
                     "MTA-STS policy without an mx line"))
    else:
        missing = [h for h in _mx_hosts(records) if not any(_matches(h, p) for p in patterns)]
        if missing:
            out.append(F("DNS-MTF-001", S.WARNING, url,
                         f"{len(missing)} MX-Host(s) der Domain passen zu keinem mx-Muster der Richtlinie",
                         f"{len(missing)} MX host(s) of the domain match no mx pattern of the policy", missing[0][:80]))
    raw_age = (fields.get("max_age") or [""])[0]
    if not raw_age.isdigit():
        out.append(F("DNS-MTF-001", S.WARNING, url, "MTA-STS-Richtlinie ohne gültiges max_age",
                     "MTA-STS policy without a valid max_age"))
    elif int(raw_age) < 86400:
        out.append(F("DNS-MTF-001", S.NOTE, url, "max_age der MTA-STS-Richtlinie liegt unter einem Tag",
                     "max_age of the MTA-STS policy is below one day", raw_age[:12]))
    elif int(raw_age) < 604800:
        out.append(F("DNS-MTF-001", S.INFO, url, "max_age der MTA-STS-Richtlinie liegt unter einer Woche",
                     "max_age of the MTA-STS policy is below one week", raw_age[:12]))
    return out


@check("TKO-FNG-001",
       title="Takeover-Fingerprints (Fehlerseiten von Fremddiensten) ## Takeover fingerprints (error pages of third-party services)",
       why="Zeigt eine Subdomain auf einen Dienst und der Dienst antwortet mit der Fehlerseite für eine nicht "
           "vergebene Ressource, kann ein Angreifer sie übernehmen und unter Ihrer Domain Inhalte ausliefern. ## If "
           "a subdomain points to a service and the service answers with the error page for an unclaimed "
           "resource, an attacker can take it over and serve content under your domain.",
       method="Für Subdomains, deren CNAME auf einen bekannten Dienst zeigt und deren Ziel noch eine Adresse hat "
              "(höchstens 5), wird die Startseite einmal abgerufen und auf typische Fehlertexte geprüft (GitHub "
              "Pages, Heroku, S3, Shopify, Surge, Bitbucket, Ghost, Fastly). Die Texte stammen aus öffentlichen "
              "Listen und sind ungeprüft; Dienste ändern sie. Subdomains werden nie erraten. ## For subdomains whose "
              "CNAME points to a known service and whose target still has an address (at most 5), the home page is "
              "fetched once and checked for typical error texts (GitHub Pages, Heroku, S3, Shopify, Surge, "
              "Bitbucket, Ghost, Fastly). The texts come from public lists and are unverified; services change "
              "them. Subdomains are never guessed.",
       logic="Fehlertext gefunden: Warnung. ## Error text found: warning.",
       fix="Den DNS-Eintrag löschen oder die Ressource beim Dienst neu anlegen, bevor es jemand anderes tut. ## "
           "Delete the DNS record or re-create the resource at the service before somebody else does.",
       refs=["https://github.com/EdOverflow/can-i-take-over-xyz",
             "https://owasp.org/www-project-web-security-testing-guide/"],
       profiles="sd", source="network")
def fingerprints(snap):
    passive = snap.extra.get("passive")
    if passive is None:
        raise CheckSkipped("no_passive_data")
    records = passive.get("takeover")
    if records is None:
        raise CheckSkipped("no_takeover_data")
    out = []
    for rec in records:
        if rec.get("matched"):
            host, service = rec.get("host", "?"), rec.get("service", "?")
            out.append(F("TKO-FNG-001", S.WARNING, snap.target.url,
                         f"Subdomain {host}: Fehlerseite von {service}, die Ressource scheint frei zu sein (Takeover-Risiko)",
                         f"Subdomain {host}: error page of {service}, the resource seems to be unclaimed (takeover risk)",
                         f"{host} → {service}"))
    return out
