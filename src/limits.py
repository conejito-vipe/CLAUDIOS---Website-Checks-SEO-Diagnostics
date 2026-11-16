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
    takeover_hosts_max: int = 20
    takeover_queries_max: int = 80
    ads_bytes_max: int = 200_000
    browser_sample_standard: int = 10
    browser_sample_deep: int = 25
    gsc_inspections: int = 100
    cooldown_seconds: int = 120
    scans_per_hour: int = 5
    scans_per_domain_day_level1: int = 3
    active_paths_max: int = 40

    def pages_for(self, level: int, profile: str = "standard") -> int:
        cap = self.pages_level2 if level == 2 else self.pages_level1
        return min(cap, self.quick_pages) if profile == "quick" else cap


LIMITS = Limits()