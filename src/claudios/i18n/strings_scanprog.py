"""UI-Texte der Scan-Anzeige: Zähler statt wiederholter Zeilen, Restzeit, Navigationsbalken, Verlauf, Codefenster."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "scan.crawl_count": "Seiten geladen: {cur} / {total}",
    "scan.link_count": "Externe Links geprüft: {cur} / {total} · {url}",
    "scan.check_count": "Prüfung {cur} / {total}: {name}",
    "scan.stage.crawl": "Seiten werden geladen …",
    "scan.stage.links": "Externe Links werden auf Erreichbarkeit geprüft (Weiterleitungen werden nicht verfolgt) …",
    "scan.stage.checks": "Prüfungen laufen (HTML, CSS, JavaScript, Browser, TLS …). Das kann mehrere Minuten dauern.",
    "scan.eta": "Geschätzte Restzeit dieses Abschnitts: ca. {time}",
    "nav.running": "Scan läuft",
    "res.live": "Scan läuft: {message}",
    "res.history_note": "Letzter gespeicherter Scan: {host} vom {date}, Wertung {score}/100. Gespeichert ist nur die "
                        "Zusammenfassung ohne Adressen. Für alle Einzelheiten starte einen neuen Scan.",
    "detail.code": "Quelltext ({url}, Zeile {line})",
    "detail.legend": "Gelb: Hinweis oder Warnung · Rot: Fehler oder kritisch · Blau: Information",
})
TEXTS["en"].update({
    "scan.crawl_count": "Pages loaded: {cur} / {total}",
    "scan.link_count": "External links checked: {cur} / {total} · {url}",
    "scan.check_count": "Check {cur} / {total}: {name}",
    "scan.stage.crawl": "Loading pages …",
    "scan.stage.links": "Checking external links for reachability (redirects are not followed) …",
    "scan.stage.checks": "Checks are running (HTML, CSS, JavaScript, browser, TLS …). This can take several minutes.",
    "scan.eta": "Estimated time left in this stage: approx. {time}",
    "nav.running": "Scan running",
    "res.live": "Scan running: {message}",
    "res.history_note": "Last saved scan: {host} from {date}, score {score}/100. Only the summary without addresses is "
                        "stored. Start a new scan for all details.",
    "detail.code": "Source ({url}, line {line})",
    "detail.legend": "Yellow: note or warning · Red: error or critical · Blue: information",
})
