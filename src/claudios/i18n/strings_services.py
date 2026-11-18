"""UI-Texte für die Seite 'Externe Dienste' und die Fortschrittsnamen der Zusatz-Probes."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.services": "Externe Dienste",
    "probe.ai": "KI-Hinweisdatei (llms.txt)", "probe.rdap": "Domainablauf (RDAP)",
    "probe.safebrowsing": "Safe Browsing (Google)", "probe.psi": "PageSpeed Insights (Google)",
    "probe.shots": "Screenshots",
    "svc.title": "Externe Dienste",
    "svc.intro": "Diese Schalter erlauben Abfragen bei Dritten, nicht bei der geprüften Website. Alles ist "
                 "standardmäßig aus. Die Abfragen an IANA und RDAP laufen über denselben Schutz wie alle anderen Zugriffe, "
                 "Safe Browsing und PageSpeed über einen eigenen Client, der nur feste Google-Hosts erreicht.",
    "svc.rdap.switch": "Domainablauf per RDAP abfragen (Standard: aus)",
    "svc.rdap.info": "Gesendet wird die registrierbare Domain (zum Beispiel beispiel.de), nie eine Unterseite. Zuerst "
                     "fragt Claudios bei IANA nach dem zuständigen Server, danach bei diesem Server nach der Domain. "
                     "Beide Server sehen deine IP-Adresse. Ergebnis ist das Ablaufdatum der Domain.",
    "svc.rdap.ask": "Beim nächsten Scan wird die registrierbare Domain an IANA und den zuständigen RDAP-Server "
                    "gesendet. Diese Server sehen deine IP-Adresse. Einschalten?",
    "svc.state.on": "RDAP ist eingeschaltet.", "svc.state.off": "RDAP ist ausgeschaltet.",
    "svc.sb.switch": "Google Safe Browsing nutzen (Standard: aus, eigener Schlüssel nötig)",
    "svc.sb.info": "Gesendet werden bis zu 5 Adressen der geprüften Website ohne Parameter an Google. Google sieht deine "
                   "IP-Adresse. Du brauchst einen eigenen API-Schlüssel (Google Cloud, Safe Browsing API). Der Schlüssel "
                   "liegt im Windows-Anmeldeinformationsspeicher, nie in einer Datei oder im Bericht.",
    "svc.sb.ask": "Beim nächsten Scan werden bis zu 5 Adressen der geprüften Website an Google Safe Browsing gesendet. "
                  "Google sieht deine IP-Adresse. Einschalten?",
    "svc.sb.key_ph": "API-Schlüssel für Safe Browsing",
    "svc.sb.save": "Schlüssel speichern", "svc.sb.delete": "Schlüssel löschen",
    "svc.sb.saved": "Ein Schlüssel ist gespeichert.", "svc.sb.none": "Es ist kein Schlüssel gespeichert.",
    "svc.sb.invalid": "Der Schlüssel sieht ungültig aus (20 bis 128 Zeichen: Buchstaben, Ziffern, - und _).",
    "svc.sb.memory": "Auf diesem System nur bis zum Programmende.",
    "svc.psi.switch": "Google PageSpeed Insights nutzen (Standard: aus)",
    "svc.psi.info": "Gesendet wird die Adresse der Startseite. Google ruft die Seite selbst ab (Lighthouse, mobil) und "
                    "liefert Messwerte und, falls vorhanden, Daten echter Besucher (CrUX). Google sieht deine "
                    "IP-Adresse. Ein Scan dauert damit bis zu 90 Sekunden länger. Ohne Schlüssel gilt ein kleines "
                    "Kontingent.",
    "svc.psi.ask": "Beim nächsten Scan wird die Adresse der Startseite an Google PageSpeed Insights gesendet, Google "
                   "ruft die Seite ab und sieht deine IP-Adresse. Einschalten?",
    "svc.local.title": "Lokale Optionen (nichts wird gesendet)",
    "svc.shots.switch": "Screenshots der Startseite speichern (Standard: aus)",
    "svc.shots.info": "Ein Browser fotografiert die Startseite am Desktop (1280 px) und mobil (390 px). Die Bilder bleiben "
                      "auf diesem Rechner, die letzten 3 Scans werden aufbewahrt. Dafür müssen Node und Playwright "
                      "installiert sein. Der Lauf verlängert den Scan um etwa eine halbe Minute.",
    "svc.shots.ask": "Beim nächsten Scan wird die Startseite im Browser geöffnet und fotografiert. Die Bilder bleiben "
                     "lokal. Einschalten?",
    "svc.shots.zip": "Screenshots des letzten Scans als ZIP speichern …",
    "svc.shots.none": "Der letzte Scan hat keine Screenshots erzeugt (Option aus, Werkzeug fehlt oder Lauf fehlgeschlagen).",
    "svc.shots.dialog": "Screenshots speichern",
})
TEXTS["en"].update({
    "nav.services": "External services",
    "probe.ai": "AI hint file (llms.txt)", "probe.rdap": "Domain expiry (RDAP)",
    "probe.safebrowsing": "Safe Browsing (Google)", "probe.psi": "PageSpeed Insights (Google)",
    "probe.shots": "Screenshots",
    "svc.title": "External services",
    "svc.intro": "These switches allow queries to third parties, not to the website being checked. Everything is off "
                 "by default. The queries to IANA and RDAP use the same protection as all other requests, Safe Browsing "
                 "and PageSpeed use their own client that only reaches fixed Google hosts.",
    "svc.rdap.switch": "Query domain expiry via RDAP (default: off)",
    "svc.rdap.info": "The registrable domain (for example example.com) is sent, never a subpage. Claudios first asks "
                     "IANA for the responsible server and then asks that server about the domain. Both servers see "
                     "your IP address. The result is the expiry date of the domain.",
    "svc.rdap.ask": "With the next scan the registrable domain will be sent to IANA and the responsible RDAP server. "
                    "These servers see your IP address. Turn it on?",
    "svc.state.on": "RDAP is on.", "svc.state.off": "RDAP is off.",
    "svc.sb.switch": "Use Google Safe Browsing (default: off, own key required)",
    "svc.sb.info": "Up to 5 addresses of the checked website without parameters are sent to Google. Google sees your IP "
                   "address. You need your own API key (Google Cloud, Safe Browsing API). The key is kept in the Windows "
                   "Credential Manager, never in a file or in the report.",
    "svc.sb.ask": "With the next scan up to 5 addresses of the checked website will be sent to Google Safe Browsing. "
                  "Google sees your IP address. Turn it on?",
    "svc.sb.key_ph": "API key for Safe Browsing",
    "svc.sb.save": "Save key", "svc.sb.delete": "Delete key",
    "svc.sb.saved": "A key is stored.", "svc.sb.none": "No key is stored.",
    "svc.sb.invalid": "The key looks invalid (20 to 128 characters: letters, digits, - and _).",
    "svc.sb.memory": "On this system only until the program closes.",
    "svc.psi.switch": "Use Google PageSpeed Insights (default: off)",
    "svc.psi.info": "The address of the home page is sent. Google fetches the page itself (Lighthouse, mobile) and returns "
                    "measurements and, if available, data of real visitors (CrUX). Google sees your IP address. A scan "
                    "takes up to 90 seconds longer. Without a key a small quota applies.",
    "svc.psi.ask": "With the next scan the address of the home page will be sent to Google PageSpeed Insights, Google "
                   "fetches the page and sees your IP address. Turn it on?",
    "svc.local.title": "Local options (nothing is sent)",
    "svc.shots.switch": "Save screenshots of the home page (default: off)",
    "svc.shots.info": "A browser photographs the home page on desktop (1280 px) and mobile (390 px). The images stay on "
                      "this computer, the last 3 scans are kept. This needs Node and Playwright to be installed. The run "
                      "makes the scan about half a minute longer.",
    "svc.shots.ask": "With the next scan the home page will be opened in the browser and photographed. The images stay "
                     "local. Turn it on?",
    "svc.shots.zip": "Save screenshots of the last scan as ZIP …",
    "svc.shots.none": "The last scan produced no screenshots (option off, tool missing or run failed).",
    "svc.shots.dialog": "Save screenshots",
})
