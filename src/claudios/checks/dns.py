"""DNS- und E-Mail-Sicherheit. Alle Daten stammen aus der Probe-Phase (nur lesende DoH-Abfragen)."""
from __future__ import annotations

import re

from ..core.dnsprobe import txt_join
from ..core.registry import check
from ._util import CheckSkipped, F, S

_NULL_MX = re.compile(r"0\s+\.")
RFC = "https://www.rfc-editor.org/rfc/"


def _dns(snap) -> dict:
    data = snap.extra.get("dns")
    if data is None:
        raise CheckSkipped("no_dns_data")
    if all(data["records"].get(k) is None for k in ("mx", "ns", "txt")):
        raise CheckSkipped("dns_unreachable")
    return data


def _rec(data: dict, key: str):
    return data["records"].get(key)


def _txt(data: dict, key: str) -> list[str]:
    return [txt_join(x) for x in (_rec(data, key) or [])]


def _has_mail(data: dict) -> bool:
    """Eine Domain hat Mail, wenn es einen MX-Eintrag gibt, der kein 'Null-MX' (0 .) ist."""
    return any(not _NULL_MX.fullmatch(m.strip()) for m in (_rec(data, "mx") or []))


def _f(cid: str, sev, snap, de: str, en: str, evidence: str = ""):
    return F(cid, sev, snap.target.url, de, en, evidence)


@check("DNS-SPF-001",
       title="SPF (Absender-Richtlinie) ## SPF (sender policy)",
       why="Ohne SPF kann jeder E-Mails im Namen der Domain versenden (Phishing). Ein 'all' ohne Einschränkung "
           "erlaubt jeden Absender, und mehr als 10 DNS-Abfragen machen den Eintrag ungültig. ## "
           "Without SPF anyone can send e-mail in the name of the domain (phishing). An unrestricted 'all' "
           "allows every sender, and more than 10 DNS lookups invalidate the record.",
       method="Liest die TXT-Einträge der Domain über DNS-over-HTTPS, sucht v=spf1, wertet den Abschluss "
              "(all oder redirect) aus und zählt DNS-abfragende Mechanismen (include, a, mx, ptr, exists, "
              "redirect) rekursiv. ## Reads the TXT records of the domain via DNS-over-HTTPS, looks for "
              "v=spf1, evaluates the terminator (all or redirect) and counts DNS-querying mechanisms "
              "(include, a, mx, ptr, exists, redirect) recursively.",
       logic="Fehlt bei einer Domain mit Mail: Warnung (ohne Mail: Hinweis). +all, mehrere Einträge oder über 10 "
             "Abfragen: Fehler. Kein Abschluss: Warnung. ?all oder ptr: Hinweis. ## Missing for a domain with "
             "mail: warning (without mail: note). +all, several records or more than 10 lookups: error. No "
             "terminator: warning. ?all or ptr: note.",
       fix="Genau einen Eintrag setzen, z. B. v=spf1 include:anbieter.example -all (ohne Mailversand: v=spf1 -all). ## "
           "Publish exactly one record, e.g. v=spf1 include:provider.example -all (without mail: v=spf1 -all).",
       refs=[RFC + "rfc7208"], profiles="sd", source="network")
def spf(snap):
    d = _dns(snap)
    if _rec(d, "txt") is None:
        raise CheckSkipped("dns_txt_unavailable")
    records = [x for x in _txt(d, "txt") if x.lower().startswith("v=spf1")]
    if not records:
        if _has_mail(d):
            return [_f("DNS-SPF-001", S.WARNING, snap, "Kein SPF-Eintrag, obwohl die Domain E-Mail nutzt",
                       "No SPF record although the domain uses e-mail")]
        return [_f("DNS-SPF-001", S.NOTE, snap,
                   "Kein SPF-Eintrag (ohne Mailversand empfohlen: v=spf1 -all)",
                   "No SPF record (without mail sending recommended: v=spf1 -all)")]
    if len(records) > 1:
        return [_f("DNS-SPF-001", S.ERROR, snap, "Mehrere SPF-Einträge (ungültig)",
                   "Several SPF records (invalid)")]
    terms = records[0].lower().split()[1:]
    out = []
    all_term = next((t for t in terms if re.fullmatch(r"[+\-~?]?all", t)), None)
    if all_term is None and not any(t.startswith("redirect=") for t in terms):
        out.append(_f("DNS-SPF-001", S.WARNING, snap, "SPF ohne Abschluss (all oder redirect)",
                      "SPF without terminator (all or redirect)", records[0][:120]))
    elif all_term in ("all", "+all"):
        out.append(_f("DNS-SPF-001", S.ERROR, snap, "SPF erlaubt jeden Absender (+all)",
                      "SPF allows every sender (+all)", records[0][:120]))
    elif all_term == "?all":
        out.append(_f("DNS-SPF-001", S.NOTE, snap, "SPF ist neutral (?all) und schützt nicht",
                      "SPF is neutral (?all) and does not protect", records[0][:120]))
    lookups = d.get("spf_lookups")
    if lookups is not None and lookups > 10:
        out.append(_f("DNS-SPF-001", S.ERROR, snap, "SPF braucht mehr als 10 DNS-Abfragen (Limit ist 10)",
                      "SPF needs more than 10 DNS lookups (limit is 10)", records[0][:120]))
    if any(t.lstrip("+-~?") == "ptr" or t.lstrip("+-~?").startswith("ptr:") for t in terms):
        out.append(_f("DNS-SPF-001", S.NOTE, snap, "SPF nutzt den veralteten Mechanismus ptr",
                      "SPF uses the deprecated mechanism ptr", records[0][:120]))
    return out


@check("DNS-DKM-001",
       title="DKIM (Mail-Signatur) ## DKIM (mail signature)",
       why="Mit DKIM signierte Mails lassen sich auf Fälschung prüfen und werden seltener als Spam eingestuft. ## "
           "Mail signed with DKIM can be verified against forgery and is less often classified as spam.",
       method="Fragt gängige Selektoren (default, google, selector1, selector2, k1, k2, s1, s2, mail, dkim) unter "
              "_domainkey ab. Selektoren lassen sich nicht auflisten: Ein Nichtfund ist nur ein Hinweis, kein Beweis. "
              "Läuft nur bei Domains mit Mail. ## Queries common selectors (default, google, selector1, selector2, "
              "k1, k2, s1, s2, mail, dkim) under _domainkey. Selectors cannot be enumerated: not finding one is "
              "only a hint, not proof. Runs only for domains with mail.",
       logic="Kein Schlüssel gefunden: Hinweis. Widerrufener Schlüssel (leeres p=): Hinweis. ## "
             "No key found: note. Revoked key (empty p=): note.",
       fix="Beim Mailanbieter DKIM aktivieren und den angezeigten TXT-Eintrag unter <selektor>._domainkey setzen. ## "
           "Enable DKIM at the mail provider and publish the TXT record shown under <selector>._domainkey.",
       refs=[RFC + "rfc6376"], profiles="sd", source="network")
def dkim(snap):
    d = _dns(snap)
    if not _has_mail(d):
        return []
    keys = [k for k in d["records"] if k.startswith("dkim:")]
    if keys and all(_rec(d, k) is None for k in keys):
        raise CheckSkipped("dns_dkim_unavailable")
    found: list[str] = []
    revoked: list[str] = []
    for key in keys:
        for rec in _txt(d, key):
            low = rec.lower().replace(" ", "")
            if "v=dkim1" in low or "p=" in low:
                found.append(key[5:])
                if re.search(r"(^|;)p=(;|$)", low):
                    revoked.append(key[5:])
                break
    out = []
    if not found:
        out.append(_f("DNS-DKM-001", S.NOTE, snap,
                      "Kein DKIM-Schlüssel unter gängigen Selektoren gefunden (kein Beweis)",
                      "No DKIM key found under common selectors (not proof)"))
    for selector in revoked:
        out.append(_f("DNS-DKM-001", S.NOTE, snap, "DKIM-Schlüssel ist widerrufen (leeres p=)",
                      "DKIM key is revoked (empty p=)", selector))
    return out


@check("DNS-DMA-001",
       title="DMARC (Umgang mit gefälschten Mails) ## DMARC (handling of forged mail)",
       why="DMARC legt fest, was Empfänger mit Mails tun, die SPF und DKIM nicht bestehen, und liefert Berichte. "
           "Große Mailanbieter erwarten es inzwischen. ## DMARC defines what recipients do with mail that fails "
           "SPF and DKIM and provides reports. Large mail providers now expect it.",
       method="Liest den TXT-Eintrag _dmarc.<domain> und wertet p, rua und pct aus. ## Reads the TXT record "
              "_dmarc.<domain> and evaluates p, rua and pct.",
       logic="Fehlt bei Mail: Warnung (ohne Mail: Hinweis). Mehrere oder ungültige Richtlinie: Fehler. p=none: "
             "Hinweis. pct unter 100: Hinweis. Ohne rua: Info. ## Missing with mail: warning (without mail: note). "
             "Several or invalid policy: error. p=none: note. pct below 100: note. Without rua: info.",
       fix="TXT-Eintrag _dmarc setzen: v=DMARC1; p=quarantine; rua=mailto:dmarc@ihre-domain.example, später p=reject. ## "
           "Publish a _dmarc TXT record: v=DMARC1; p=quarantine; rua=mailto:dmarc@your-domain.example, later p=reject.",
       refs=[RFC + "rfc7489"], profiles="sd", source="network")
def dmarc(snap):
    d = _dns(snap)
    if _rec(d, "dmarc") is None:
        raise CheckSkipped("dns_dmarc_unavailable")
    mail = _has_mail(d)
    records = [x for x in _txt(d, "dmarc") if x.lower().startswith("v=dmarc1")]
    if not records:
        return [_f("DNS-DMA-001", S.WARNING if mail else S.NOTE, snap, "Kein DMARC-Eintrag", "No DMARC record")]
    if len(records) > 1:
        return [_f("DNS-DMA-001", S.ERROR, snap, "Mehrere DMARC-Einträge (ungültig)",
                   "Several DMARC records (invalid)")]
    if not mail:
        return []
    tags: dict[str, str] = {}
    for part in records[0].split(";"):
        key, _, value = part.strip().partition("=")
        if key:
            tags[key.strip().lower()] = value.strip().lower()
    policy = tags.get("p")
    out = []
    if policy not in ("none", "quarantine", "reject"):
        out.append(_f("DNS-DMA-001", S.ERROR, snap, "DMARC-Richtlinie (p) fehlt oder ist ungültig",
                      "DMARC policy (p) missing or invalid", records[0][:120]))
    elif policy == "none":
        out.append(_f("DNS-DMA-001", S.NOTE, snap, "DMARC nur im Beobachtungsmodus (p=none)",
                      "DMARC in monitoring mode only (p=none)", records[0][:120]))
    pct = tags.get("pct", "")
    if policy in ("quarantine", "reject") and pct.isdigit() and int(pct) < 100:
        out.append(_f("DNS-DMA-001", S.NOTE, snap, "DMARC gilt nur für einen Teil der Mails (pct unter 100)",
                      "DMARC applies to only part of the mail (pct below 100)", records[0][:120]))
    if "rua" not in tags:
        out.append(_f("DNS-DMA-001", S.INFO, snap, "DMARC ohne Berichtsadresse (rua)",
                      "DMARC without report address (rua)"))
    return out


@check("DNS-CAA-001",
       title="CAA (erlaubte Zertifizierungsstellen) ## CAA (allowed certificate authorities)",
       why="Ohne CAA darf jede Zertifizierungsstelle Zertifikate für die Domain ausstellen. CAA verringert das "
           "Risiko falsch ausgestellter Zertifikate. ## Without CAA every certificate authority may issue "
           "certificates for the domain. CAA reduces the risk of mis-issued certificates.",
       method="Fragt CAA-Einträge der Domain ab. ## Queries CAA records of the domain.",
       logic="Kein CAA-Eintrag: Hinweis. ## No CAA record: note.",
       fix="CAA-Eintrag setzen, z. B. 0 issue \"letsencrypt.org\". ## Publish a CAA record, e.g. 0 issue \"letsencrypt.org\".",
       refs=[RFC + "rfc8659"], profiles="sd", source="network")
def caa(snap):
    d = _dns(snap)
    value = _rec(d, "caa")
    if value is None:
        raise CheckSkipped("dns_caa_unavailable")
    if not value:
        return [_f("DNS-CAA-001", S.NOTE, snap, "Kein CAA-Eintrag: jede Zertifizierungsstelle darf ausstellen",
                   "No CAA record: any certificate authority may issue")]
    return []


@check("DNS-MTA-001",
       title="MTA-STS und TLS-RPT ## MTA-STS and TLS-RPT",
       why="MTA-STS erzwingt verschlüsselten Mailtransport zwischen Servern, TLS-RPT meldet Probleme dabei. ## "
           "MTA-STS enforces encrypted mail transport between servers, TLS-RPT reports problems with it.",
       method="Sucht die TXT-Einträge _mta-sts und _smtp._tls (nur bei Domains mit Mail). Die Richtliniendatei "
              "selbst wird nicht abgerufen. ## Looks for the TXT records _mta-sts and _smtp._tls (only for "
              "domains with mail). The policy file itself is not fetched.",
       logic="Fehlt: Info. ## Missing: info.",
       fix="TXT _mta-sts: v=STSv1; id=<zahl> und eine Richtliniendatei unter mta-sts.<domain> bereitstellen; TXT "
           "_smtp._tls: v=TLSRPTv1; rua=mailto:... ## Publish TXT _mta-sts: v=STSv1; id=<number> plus a policy "
           "file at mta-sts.<domain>; TXT _smtp._tls: v=TLSRPTv1; rua=mailto:...",
       refs=[RFC + "rfc8461", RFC + "rfc8460"], profiles="sd", source="network")
def mta_sts(snap):
    d = _dns(snap)
    if not _has_mail(d):
        return []
    if _rec(d, "mta_sts") is None and _rec(d, "tls_rpt") is None:
        raise CheckSkipped("dns_mta_unavailable")
    out = []
    if not any(x.lower().startswith("v=stsv1") for x in _txt(d, "mta_sts")):
        out.append(_f("DNS-MTA-001", S.INFO, snap, "Kein MTA-STS-Eintrag", "No MTA-STS record"))
    if not any(x.lower().startswith("v=tlsrptv1") for x in _txt(d, "tls_rpt")):
        out.append(_f("DNS-MTA-001", S.INFO, snap, "Kein TLS-RPT-Eintrag", "No TLS-RPT record"))
    return out


@check("DNS-SEC-001",
       title="DNSSEC ## DNSSEC",
       why="DNSSEC schützt vor gefälschten DNS-Antworten, mit denen Besucher auf falsche Server umgeleitet werden "
           "könnten. ## DNSSEC protects against forged DNS answers that could redirect visitors to wrong servers.",
       method="Fragt den DS-Eintrag der Domain in der übergeordneten Zone ab (ein DS-Eintrag zeigt, dass die Zone "
              "signiert ist). Die Signaturen selbst werden nicht geprüft. ## Queries the DS record of the domain in "
              "the parent zone (a DS record shows that the zone is signed). The signatures themselves are not "
              "validated.",
       logic="Kein DS-Eintrag: Hinweis. ## No DS record: note.",
       fix="DNSSEC beim DNS-Anbieter aktivieren und den DS-Eintrag bei der Domain-Registrierung hinterlegen. ## "
           "Enable DNSSEC at the DNS provider and register the DS record with the domain registrar.",
       refs=[RFC + "rfc4033"], profiles="sd", source="network")
def dnssec(snap):
    d = _dns(snap)
    value = _rec(d, "ds")
    if value is None:
        raise CheckSkipped("dns_ds_unavailable")
    if not value:
        return [_f("DNS-SEC-001", S.NOTE, snap, "DNSSEC nicht aktiviert (kein DS-Eintrag)",
                   "DNSSEC not enabled (no DS record)")]
    return []


@check("DNS-BAS-001",
       title="DNS-Basis (Nameserver, IPv6) ## DNS basics (name servers, IPv6)",
       why="Mit nur einem Nameserver fällt die Domain bei einem Ausfall komplett aus. IPv6 macht die Seite für "
           "Netze erreichbar, die kein IPv4 mehr bieten. ## With only one name server the domain goes completely "
           "down on an outage. IPv6 makes the site reachable for networks that no longer offer IPv4.",
       method="Zählt die NS-Einträge der Domain und sucht einen AAAA-Eintrag für den geprüften Host. TTL-Werte "
              "werden nicht ausgewertet. ## Counts the NS records of the domain and looks for an AAAA record for "
              "the checked host. TTL values are not evaluated.",
       logic="Weniger als 2 Nameserver: Warnung. Kein AAAA-Eintrag: Info. ## Fewer than 2 name servers: warning. "
             "No AAAA record: info.",
       fix="Mindestens zwei Nameserver (am besten bei verschiedenen Anbietern) und einen AAAA-Eintrag einrichten. ## "
           "Set up at least two name servers (ideally at different providers) and an AAAA record.",
       refs=[RFC + "rfc2182", RFC + "rfc3596"], profiles="sd", source="network")
def dns_basics(snap):
    d = _dns(snap)
    ns, aaaa = _rec(d, "ns"), _rec(d, "aaaa")
    if ns is None and aaaa is None:
        raise CheckSkipped("dns_basics_unavailable")
    out = []
    if ns is not None and len({x.lower() for x in ns}) < 2:
        out.append(_f("DNS-BAS-001", S.WARNING, snap, "Weniger als 2 Nameserver (kein Ausfallschutz)",
                      "Fewer than 2 name servers (no redundancy)"))
    if aaaa is not None and not aaaa:
        out.append(_f("DNS-BAS-001", S.INFO, snap, "Kein IPv6-Eintrag (AAAA)", "No IPv6 record (AAAA)"))
    return out