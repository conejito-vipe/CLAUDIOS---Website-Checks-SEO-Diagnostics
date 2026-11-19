"""UI-Texte für den Einrichtungs-Assistenten."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "nav.setup": "Einrichtung",
    "setup.title": "Einrichtung",
    "setup.intro": "Drei kurze Schritte bis zum ersten Scan. Nichts davon ist Pflicht: Ohne Werkzeuge laufen viele "
                   "Prüfungen als „nicht ausgeführt“ und zählen nie als bestanden.",
    "setup.step1": "1. Werkzeuge installieren (Java, Node, W3C-Prüfer, ESLint, Browser und weitere):",
    "setup.status": "{ok} von {total} Komponenten installiert.",
    "setup.to_components": "Zu „Komponenten“",
    "setup.step2": "2. Optional: Mit Google anmelden, um Stufe 2 für eigene Domains freizuschalten.",
    "setup.to_gsc": "Zur Search Console",
    "setup.step3": "3. Den ersten Scan deiner eigenen Website starten.",
    "setup.to_scan": "Zum Scan",
    "setup.notes": "Hinweise: sslyze lässt sich nur installieren, wenn Claudios aus dem Quellcode gestartet wird, der "
                   "Windows-Build bringt noch keine eigene Python-Laufzeit mit. Der Chromium-Download des "
                   "Browser-Pakets ist nicht durch eine eigene Prüfsumme von Claudios gesichert.",
    "setup.finish": "Einrichtung abschließen (nicht mehr automatisch zeigen)",
})

TEXTS["en"].update({
    "nav.setup": "Setup",
    "setup.title": "Setup",
    "setup.intro": "Three short steps to your first scan. None of them is mandatory: without tools many checks run "
                   "as 'not executed' and never count as passed.",
    "setup.step1": "1. Install tools (Java, Node, W3C checkers, ESLint, browser and more):",
    "setup.status": "{ok} of {total} components installed.",
    "setup.to_components": "Go to 'Components'",
    "setup.step2": "2. Optional: sign in with Google to enable level 2 for your own domains.",
    "setup.to_gsc": "Go to Search Console",
    "setup.step3": "3. Start the first scan of your own website.",
    "setup.to_scan": "Go to Scan",
    "setup.notes": "Notes: sslyze can only be installed when Claudios is started from the source code, the Windows "
                   "build does not yet ship its own Python runtime. The Chromium download of the browser package is "
                   "not secured by a checksum of Claudios.",
    "setup.finish": "Finish setup (do not show automatically again)",
})
