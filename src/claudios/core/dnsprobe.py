"""DNS-Sammlung nur über DNS-over-HTTPS und nur lesend. Füllt snap.extra['dns'] für die DNS-Prüfungen."""
from __future__ import annotations

import asyncio
import re

from .limits import LIMITS

DKIM_SELECTORS = ("default", "google", "selector1", "selector2", "k1", "k2", "s1", "s2", "mail", "dkim")
_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
_MAX_SPF_DEPTH = 5


def txt_join(rdata: str) -> str:
    """TXT-Datensätze bestehen aus mehreren Zeichenketten in Anführungszeichen: zusammenfügen."""
    parts = _QUOTED.findall(rdata)
    return "".join(parts) if parts else rdata.strip().strip('"')


class DnsCollector:
    def __init__(self, resolver) -> None:
        self.resolver = resolver
        self.count = 0
        self._sem = asyncio.Semaphore(4)

    async def get(self, name: str, rtype: str) -> list[str] | None:
        """None = unbekannt (Fehler oder Abfragelimit), [] = der Eintrag existiert nicht."""
        if self.count >= LIMITS.dns_queries_max:
            return None
        self.count += 1
        async with self._sem:
            try:
                return await self.resolver.query(name, rtype)
            except Exception:  # noqa: BLE001 – ein DNS-Fehler bedeutet nur: unbekannt
                return None


def _spf_name(term: str) -> str | None:
    if term.startswith("include:"):
        return term.split(":", 1)[1]
    if term.startswith("redirect="):
        return term.split("=", 1)[1]
    return None


async def count_spf_lookups(collector: DnsCollector, record: str, depth: int = 0) -> int:
    """Zählt DNS-abfragende SPF-Mechanismen rekursiv; bricht nach mehr als 10 ab."""
    total = 0
    for raw in record.split()[1:]:
        term = raw.lstrip("+-~?").lower()
        name = _spf_name(term)
        if name is not None:
            total += 1
            if depth < _MAX_SPF_DEPTH and name:
                for txt in await collector.get(name, "TXT") or []:
                    sub = txt_join(txt)
                    if sub.lower().startswith("v=spf1"):
                        total += await count_spf_lookups(collector, sub, depth + 1)
                        break
        elif term in ("a", "mx", "ptr") or term.startswith(("a:", "a/", "mx:", "mx/", "ptr:", "exists:")):
            total += 1
        if total > 10:
            return total
    return total


async def collect_dns(resolver, host: str, domain: str) -> dict:
    collector = DnsCollector(resolver)
    wanted: dict[str, tuple[str, str]] = {
        "mx": (domain, "MX"),
        "ns": (domain, "NS"),
        "txt": (domain, "TXT"),
        "dmarc": (f"_dmarc.{domain}", "TXT"),
        "caa": (domain, "CAA"),
        "ds": (domain, "DS"),
        "aaaa": (host, "AAAA"),
        "mta_sts": (f"_mta-sts.{domain}", "TXT"),
        "tls_rpt": (f"_smtp._tls.{domain}", "TXT"),
        "bimi": (f"default._bimi.{domain}", "TXT"),
        "tlsa": (f"_443._tcp.{host}", "TLSA"),
    }
    for selector in DKIM_SELECTORS:
        wanted[f"dkim:{selector}"] = (f"{selector}._domainkey.{domain}", "TXT")
    keys = list(wanted)
    values = await asyncio.gather(*(collector.get(*wanted[key]) for key in keys))
    records = dict(zip(keys, values, strict=True))
    lookups = None
    spf = [txt_join(x) for x in records.get("txt") or [] if txt_join(x).lower().startswith("v=spf1")]
    if len(spf) == 1:
        lookups = await count_spf_lookups(collector, spf[0])
    return {"domain": domain, "host": host, "records": records, "spf_lookups": lookups,
            "queries": collector.count}
