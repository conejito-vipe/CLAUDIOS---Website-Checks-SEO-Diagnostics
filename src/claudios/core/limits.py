"""Feste Grenzen. Bewusst Konstanten im Code, NICHT in Einstellungen oder Konfigurationsdateien."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    max_depth: int = 6                      # Startseite = Ebene 1
    pages_level1: int = 25                  # ohne Verifizierung
    pages_level2: int = 100                 # mit Google-Verifizierung
    quick_pages: int = 5
    requests_per_second: float = 2.0
    requests_per_second_max: float = 5.0
    connections_per_host: int = 2
    request_timeout: float = 15.0
    max_response_bytes: int = 5 * 1024 * 1024
    max_html_bytes: int = 2 * 1024 * 1024   # Analysegröße je Seite
    max_scan_bytes: int = 200 * 1024 * 1024
    max_redirects: int = 10
    max_query_variants_per_path: int = 3
    max_queued_urls: int = 5000
    max_external_links_stored: int = 500
    external_links_checked: int = 200
    external_links_budget_seconds: float = 300.0
    dns_queries_max: int = 40
    rebind_hosts_max: int = 10              # Hosts, die vor/nach einem Werkzeug-Lauf erneut geprüft werden
    foreign_hosts_max: int = 30             # Fremd-Hosts, die nach Browser/ZAP erneut aufgelöst werden
    foreign_budget_seconds: float = 45.0    # Zeitbudget dieser Prüfung
    foreign_workers: int = 6                # gleichzeitige DNS-Abfragen dabei
    takeover_hosts_max: int = 20
    takeover_queries_max: int = 80
    passive_takeover_hosts: int = 5         # Subdomains mit Fremddienst, deren Fehlerseite geprüft wird
    passive_body_max: int = 20_000          # Bytes je Anfrage der Zusatzdateien (security.txt, MTA-STS, Favicon)
    llms_body_max: int = 200_000            # Bytes der llms.txt
    rdap_body_max: int = 1_000_000          # Bytes je RDAP-Antwort (IANA-Liste und Domain-Abfrage)
    safebrowsing_urls_max: int = 5          # Adressen der eigenen Website je Safe-Browsing-Abfrage
    safebrowsing_body_max: int = 200_000    # Bytes der Safe-Browsing-Antwort
    third_party_timeout_seconds: float = 30.0   # Zeitlimit für feste Google-Dienste (Safe Browsing)
    psi_timeout_seconds: float = 90.0       # PageSpeed braucht oft 10 bis 40 Sekunden
    psi_body_max: int = 3_000_000           # Bytes der PageSpeed-Antwort
    shots_keep: int = 3                     # aufbewahrte Screenshot-Ordner (je Scan einer)
    shot_bytes_max: int = 5_000_000         # Größe je Screenshot
    ads_bytes_max: int = 200_000
    sitemap_bytes_max: int = 2_000_000
    sitemap_urls_stored: int = 2000
    sitemap_urls_checked: int = 20
    assets_css_max: int = 6
    assets_js_max: int = 10
    assets_bytes_max: int = 500_000
    tool_timeout_seconds: float = 120.0
    tool_output_max: int = 2_000_000
    tool_total_seconds: float = 1800.0      # Gesamtzeit aller Läufe von Browser, ZAP und sslyze je Scan
    tool_min_pause_seconds: float = 15.0    # Mindestpause zwischen zwei solchen Läufen
    tool_min_run_seconds: float = 30.0      # weniger Restzeit: kein weiterer Lauf
    tool_runs_per_kind: int = 4             # Läufe je Werkzeugart und Scan (Browser: Chromium, Bilder, Engines)
    browser_timeout_seconds: float = 60.0
    sslyze_timeout_seconds: float = 300.0
    browser_sample_standard: int = 10
    browser_sample_deep: int = 25
    gsc_inspections: int = 10               # URL-Inspektionen je Scan (Search Console)
    cooldown_seconds: int = 30              # Abkühlzeit zwischen zwei Scans
    scans_per_hour: int = 5
    scans_per_domain_day_level1: int = 5
    scans_per_domain_day_level2: int = 12
    audit_tamper_lock_seconds: int = 10800  # Sperre, wenn das Protokoll gelöscht oder verändert wurde
    active_paths_max: int = 40
    history_max_per_domain: int = 20        # gespeicherte Scan-Zusammenfassungen je Domain (nur mit Schalter)

    def pages_for(self, level: int, profile: str = "standard") -> int:
        cap = self.pages_level2 if level == 2 else self.pages_level1
        return min(cap, self.quick_pages) if profile == "quick" else cap


LIMITS = Limits()
