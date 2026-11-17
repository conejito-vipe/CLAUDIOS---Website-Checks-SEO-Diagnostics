"""UI-Texte für die Search-Console-Seite."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.gsc": "Search Console", "probe.gsc": "Search-Console-Daten",
    "gsc.title": "Google Search Console und Stufe 2",
    "gsc.intro": "Mit der Anmeldung beweist du, dass die Domain dir gehört (Inhaber- oder Vollzugriff in der Search "
                 "Console). Erst dann gibt es Stufe 2: aktive Prüfungen, bis zu 100 Seiten und Search-Console-Daten. "
                 "Dein Google-Passwort sieht Claudios nie, die Anmeldung läuft im Browser, angefordert wird nur "
                 "Lesezugriff. Das Token bleibt im Arbeitsspeicher, außer du wählst „angemeldet bleiben“. Ein eigenes "
                 "Google-Cloud-Projekt ist nötig, siehe docs/GOOGLE_SETUP.md.",
    "gsc.client.none": "Es ist noch kein Google-Client importiert.",
    "gsc.client.ok": "Ein Google-Client (client_secret.json) ist importiert.",
    "gsc.import_client": "client_secret.json importieren …",
    "gsc.signin": "Mit Google anmelden", "gsc.signout": "Abmelden",
    "gsc.signin_wait": "Warte auf die Anmeldung im Browser …",
    "gsc.remember": "Angemeldet bleiben (Token im Windows-Anmeldeinformationsspeicher)",
    "gsc.remember_na": "Angemeldet bleiben (auf diesem System nicht verfügbar)",
    "gsc.status.out": "Nicht angemeldet.",
    "gsc.status.in": "Angemeldet. {count} Properties, davon {eligible} mit Inhaber- oder Vollzugriff.",
    "gsc.sites": "Deine Properties:", "gsc.refresh": "Properties neu laden",
    "gsc.level2": "Stufe 2 für verifizierte Domains verwenden (gilt bis zum Programmende)",
    "gsc.level2_ask": "Stufe 2 schaltet aktive Prüfungen frei (feste Pfadliste, TLS-Angriffstests, ZAP) und lädt "
                      "bis zu 100 Seiten. Verwende sie nur für Domains, die dir gehören. Vor jedem Scan wird die "
                      "Berechtigung neu geprüft. Aktivieren?",
    "gsc.level2_on": "Stufe 2 ist aktiv: Scans von Domains in deinen Properties laufen mit Stufe 2.",
    "gsc.csv_import": "CSV-Auswertung importieren …",
    "gsc.csv_ok": "{count} Seiten aus der CSV-Datei importiert (nur im Arbeitsspeicher).",
    "gsc.csv_hint": "Alternative ohne Anmeldung: Seiten-Datei aus dem Search-Console-Export (ZIP vorher entpacken).",
    "gsc.dialog_json": "client_secret.json wählen", "gsc.dialog_csv": "Seiten-CSV wählen",
})

TEXTS["en"].update({
    "nav.gsc": "Search Console", "probe.gsc": "Search Console data",
    "gsc.title": "Google Search Console and level 2",
    "gsc.intro": "By signing in you prove that the domain belongs to you (owner or full access in Search Console). "
                 "Only then is there level 2: active checks, up to 100 pages and Search Console data. Claudios never "
                 "sees your Google password, the sign-in happens in your browser, only read access is requested. The "
                 "token stays in memory unless you choose 'stay signed in'. You need your own Google Cloud project, "
                 "see docs/GOOGLE_SETUP.md.",
    "gsc.client.none": "No Google client has been imported yet.",
    "gsc.client.ok": "A Google client (client_secret.json) is imported.",
    "gsc.import_client": "Import client_secret.json …",
    "gsc.signin": "Sign in with Google", "gsc.signout": "Sign out",
    "gsc.signin_wait": "Waiting for the sign-in in your browser …",
    "gsc.remember": "Stay signed in (token in the Windows Credential Manager)",
    "gsc.remember_na": "Stay signed in (not available on this system)",
    "gsc.status.out": "Not signed in.",
    "gsc.status.in": "Signed in. {count} properties, {eligible} of them with owner or full access.",
    "gsc.sites": "Your properties:", "gsc.refresh": "Reload properties",
    "gsc.level2": "Use level 2 for verified domains (valid until the program closes)",
    "gsc.level2_ask": "Level 2 enables active checks (fixed path list, TLS attack tests, ZAP) and loads up to 100 "
                      "pages. Use it only for domains that belong to you. The authorisation is re-checked before "
                      "every scan. Enable?",
    "gsc.level2_on": "Level 2 is active: scans of domains in your properties run with level 2.",
    "gsc.csv_import": "Import CSV report …",
    "gsc.csv_ok": "{count} pages imported from the CSV file (in memory only).",
    "gsc.csv_hint": "Alternative without sign-in: pages file from the Search Console export (unzip it first).",
    "gsc.dialog_json": "Choose client_secret.json", "gsc.dialog_csv": "Choose pages CSV",
})
