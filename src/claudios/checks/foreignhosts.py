"""Hinweis auf Fremdserver, die erst nachträglich als nicht öffentlich erkannt wurden (core/foreign.py).
Die Daten stammen aus dem Browser-Lauf (checks/_browser.py), dem ZAP-Lauf (core/probe_zap.py) und dem
Browser-Vergleich (core/probe_engines.py)."""
from __future__ import annotations

from ..core.registry import check
from ._browser import browser_data
from ._util import CheckSkipped, F, S

NEEDS = ("node", "playwright")


@check("BRW-FRN-001",
       title="Fremdserver mit nicht öffentlicher Adresse ## Third-party hosts with a non-public address",
       why="Chromium, Firefox, WebKit und ZAP lösen die Namen von Fremdservern selbst auf. Zeigt ein Name auf eine "
           "private oder lokale Adresse, spricht der Browser das eigene Netz des Besuchers an. Das ist ein Hinweis auf "
           "eine Fehlkonfiguration oder auf einen Angriff über DNS-Rebinding. ## Chromium, Firefox, WebKit and ZAP "
           "resolve the names of third-party hosts themselves. If a name points to a private or local address, the "
           "browser talks to the visitor's own network. This hints at a misconfiguration or at a DNS rebinding attack.",
       method="Nach den Browser-Läufen und dem ZAP-Lauf löst Claudios jeden beobachteten Fremd-Host erneut per "
              "DNS-over-HTTPS auf (höchstens 30 Hosts, 45 Sekunden). Zeigt einer auf eine nicht öffentliche Adresse, "
              "werden seine Daten aus dem Ergebnis entfernt. Der Zugriff selbst war da schon geschehen: die Prüfung "
              "erkennt ihn, sie verhindert ihn nicht. Hosts ohne DNS-Antwort gelten als unbekannt. Fehlen alle Daten, "
              "gilt die Prüfung als nicht ausgeführt. ## After the browser runs and the ZAP run Claudios resolves every "
              "observed third-party host again via DNS over HTTPS (at most 30 hosts, 45 seconds). If one points to a "
              "non-public address, its data is removed from the result. The access had already happened: the check "
              "detects it, it does not prevent it. Hosts without a DNS answer count as unknown. Without any data the "
              "check counts as not executed.",
       logic="Host zeigt auf eine nicht öffentliche Adresse: Warnung. Hosts, die wegen der Grenzen nicht geprüft wurden: "
             "Info. ## Host points to a non-public address: warning. Hosts not checked because of the limits: info.",
       fix="Den eingebundenen Dienst prüfen und den Eintrag entfernen oder den DNS-Eintrag des Anbieters klären. "
           "## Check the embedded service and remove it, or clarify the DNS record with the provider.",
       refs=["https://en.wikipedia.org/wiki/DNS_rebinding"],
       profiles="sd", source="tool", needs=NEEDS)
def foreign_hosts(snap):
    try:
        browser = browser_data(snap)
    except CheckSkipped:
        browser = None
    zap = snap.extra.get("zap")
    zap = zap if isinstance(zap, dict) and not zap.get("skip") else None
    engines = snap.extra.get("engines")
    engines = engines if isinstance(engines, dict) and not engines.get("skip") else None
    if browser is None and zap is None and engines is None:
        raise CheckSkipped("no_browser_data")
    private: dict[str, str] = {}
    unchecked = 0
    for source, data in (("Browser", browser), ("ZAP", zap), ("Firefox/WebKit", engines)):
        if not data:
            continue
        for host in data.get("foreign_private") or []:
            private.setdefault(str(host)[:100], source)
        unchecked += int(data.get("foreign_unchecked") or 0)
    url, out = snap.target.url, []
    for host, source in sorted(private.items()):
        out.append(F("BRW-FRN-001", S.WARNING, url,
                     f"Der Fremdserver {host} zeigt auf eine nicht öffentliche Adresse, seine Daten wurden verworfen",
                     f"The third-party host {host} points to a non-public address, its data was discarded", source))
    if unchecked:
        out.append(F("BRW-FRN-001", S.INFO, url,
                     f"{unchecked} Fremd-Host(s) wurden wegen der Grenzen nicht geprüft",
                     f"{unchecked} third-party host(s) were not checked because of the limits"))
    return out
