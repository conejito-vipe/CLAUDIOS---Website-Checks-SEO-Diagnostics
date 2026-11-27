"""UI-Texte der Scan-Seite: Stufen, Profile, Abkühlzeit, Experteneinstellungen (überschreibt scan.google aus strings.py)."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "scan.google": "Mit Google verifizieren (Stufe 2) …",
    "scan.level1": "Stufe 1 (Selbstauskunft): höchstens {pages} Seiten und {depth} Ebenen, nur passive Prüfungen. "
                   "Aktive Prüfungen und die Search Console gibt es mit Stufe 2 (Seite Search Console).",
    "scan.level_armed": "Stufe 2 ist eingeschaltet: Scans von Domains in deinen Properties laufen mit Stufe 2 "
                        "(höchstens {pages} Seiten und {depth} Ebenen, mit aktiven Prüfungen).",
    "scan.level2": "Stufe 2 (verifiziert über {prop}): höchstens {pages} Seiten und {depth} Ebenen, mit aktiven "
                   "Prüfungen und Search-Console-Daten. Die Berechtigung wird vor dem Scan live geprüft.",
    "scan.level_nomatch": "Stufe 2 ist eingeschaltet, aber keine deiner Properties mit Inhaber- oder Vollzugriff "
                          "deckt diese Domain ab. Der Scan würde abgelehnt.",
    "scan.done_level": "Scan beendet: {status} (Stufe {level}).",
    "scan.profile_info.quick": "Schnell: höchstens {quick} Seiten, kürzeste Dauer. Gedacht für einen ersten Eindruck "
                               "der Grundlagen. Welche Prüfung in welchem Profil läuft, steht im Handbuch bei jeder "
                               "Prüfung.",
    "scan.profile_info.standard": "Standard: bis zu {pages} Seiten (Stufe 1) beziehungsweise {pages2} Seiten "
                                  "(Stufe 2), {depth} Ebenen. Alle regulären Prüfungen: HTML, CSS, JavaScript, "
                                  "Sicherheit, Datenschutz, SEO, DNS und TLS. Dazu Browser-Läufe mit einer Stichprobe "
                                  "von {sample} Seiten (Konsole, Barrierefreiheit, Darstellung), soweit die "
                                  "Komponenten installiert sind.",
    "scan.profile_info.deep": "Tief: wie Standard, aber mit einer Browser-Stichprobe von {deep} Seiten und zusätzlichen, "
                              "langsameren Prüfungen, zum Beispiel dem Vergleich mit Firefox und WebKit. Dauert "
                              "deutlich länger.",
    "scan.cooldown": "Nächster Scan in {seconds} s möglich (Abkühlzeit).",
    "scan.expert": "Experteneinstellungen",
    "scan.expert.intro": "Externe Dienste senden Daten an Dritte und sind standardmäßig aus. Ist einer eingeschaltet, "
                         "fragt CLAUDIOS vor jedem Scan noch einmal nach. Dauerhaft ändern: Einstellungen (Zahnrad oben) → Experteneinstellungen.",
    "scan.expert.keys": "Schlüssel verwalten (Einstellungen) …",
    "scan.expert.nokey_sb": "Safe Browsing braucht einen eigenen Schlüssel, sonst wird die Prüfung übersprungen.",
    "scan.expert.nokey_psi": "PageSpeed hat ohne eigenen Schlüssel kaum Kontingent (HTTP 429), die Prüfung wird dann "
                             "übersprungen.",
    "scan.ext_ask": "Dieser Scan sendet Daten an Dritte: {names}. Die Dienste sehen deine IP-Adresse. Fortfahren?",
    "splash.doh_warn": "DNS über HTTPS ist in diesem Programm nicht verfügbar. Scans können deshalb keine Domain "
                       "auflösen. Bitte melde das zusammen mit der Datei claudios.log.",
})
TEXTS["en"].update({
    "scan.google": "Verify with Google (level 2) …",
    "scan.level1": "Level 1 (self-declaration): at most {pages} pages and {depth} levels, passive checks only. "
                   "Active checks and Search Console are available with level 2 (Search Console page).",
    "scan.level_armed": "Level 2 is on: scans of domains in your properties run with level 2 "
                        "(at most {pages} pages and {depth} levels, with active checks).",
    "scan.level2": "Level 2 (verified via {prop}): at most {pages} pages and {depth} levels, with active checks "
                   "and Search Console data. The authorisation is checked live before the scan.",
    "scan.level_nomatch": "Level 2 is on, but none of your properties with owner or full access covers this "
                          "domain. The scan would be refused.",
    "scan.done_level": "Scan finished: {status} (level {level}).",
    "scan.profile_info.quick": "Quick: at most {quick} pages, shortest duration. Meant as a first impression of the "
                               "basics. Which check runs in which profile is listed in the manual for every check.",
    "scan.profile_info.standard": "Standard: up to {pages} pages (level 1) or {pages2} pages (level 2), {depth} "
                                  "levels. All regular checks: HTML, CSS, JavaScript, security, privacy, SEO, DNS and "
                                  "TLS. Plus browser runs with a sample of {sample} pages (console, accessibility, "
                                  "layout), as far as the components are installed.",
    "scan.profile_info.deep": "Deep: like Standard, but with a browser sample of {deep} pages and additional, slower "
                              "checks, for example the comparison with Firefox and WebKit. Takes considerably longer.",
    "scan.cooldown": "Next scan possible in {seconds} s (cool-down).",
    "scan.expert": "Expert settings",
    "scan.expert.intro": "External services send data to third parties and are off by default. If one is on, "
                         "CLAUDIOS asks again before every scan. Permanent changes: Settings (gear at the top) → Expert settings.",
    "scan.expert.keys": "Manage keys (Settings) …",
    "scan.expert.nokey_sb": "Safe Browsing needs your own key, otherwise the check is skipped.",
    "scan.expert.nokey_psi": "PageSpeed has hardly any quota without your own key (HTTP 429), the check is then "
                             "skipped.",
    "scan.ext_ask": "This scan sends data to third parties: {names}. The services see your IP address. Continue?",
    "splash.doh_warn": "DNS over HTTPS is not available in this program. Scans therefore cannot resolve a domain. "
                       "Please report this together with the file claudios.log.",
})
