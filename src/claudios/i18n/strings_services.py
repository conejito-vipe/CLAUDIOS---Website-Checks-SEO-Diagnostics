"""UI-Texte für die Seite 'Externe Dienste' und die Fortschrittsnamen der Probes ai und rdap."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.services": "Externe Dienste",
    "probe.ai": "KI-Hinweisdatei (llms.txt)", "probe.rdap": "Domainablauf (RDAP)",
    "svc.title": "Externe Dienste",
    "svc.intro": "Diese Schalter erlauben Abfragen bei Dritten, nicht bei der geprüften Website. Alles ist "
                 "standardmäßig aus. Die Abfragen laufen über denselben Schutz wie alle anderen Zugriffe.",
    "svc.rdap.switch": "Domainablauf per RDAP abfragen (Standard: aus)",
    "svc.rdap.info": "Gesendet wird die registrierbare Domain (zum Beispiel beispiel.de), nie eine Unterseite. Zuerst "
                     "fragt Claudios bei IANA nach dem zuständigen Server, danach bei diesem Server nach der Domain. "
                     "Beide Server sehen deine IP-Adresse. Ergebnis ist das Ablaufdatum der Domain.",
    "svc.rdap.ask": "Beim nächsten Scan wird die registrierbare Domain an IANA und den zuständigen RDAP-Server "
                    "gesendet. Diese Server sehen deine IP-Adresse. Einschalten?",
    "svc.state.on": "RDAP ist eingeschaltet.", "svc.state.off": "RDAP ist ausgeschaltet.",
})
TEXTS["en"].update({
    "nav.services": "External services",
    "probe.ai": "AI hint file (llms.txt)", "probe.rdap": "Domain expiry (RDAP)",
    "svc.title": "External services",
    "svc.intro": "These switches allow queries to third parties, not to the website being checked. Everything is off "
                 "by default. The queries use the same protection as all other requests.",
    "svc.rdap.switch": "Query domain expiry via RDAP (default: off)",
    "svc.rdap.info": "The registrable domain (for example example.com) is sent, never a subpage. Claudios first asks "
                     "IANA for the responsible server and then asks that server about the domain. Both servers see "
                     "your IP address. The result is the expiry date of the domain.",
    "svc.rdap.ask": "With the next scan the registrable domain will be sent to IANA and the responsible RDAP server. "
                    "These servers see your IP address. Turn it on?",
    "svc.state.on": "RDAP is on.", "svc.state.off": "RDAP is off.",
})
