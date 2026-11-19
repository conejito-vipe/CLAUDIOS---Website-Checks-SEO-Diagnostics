"""Autorenname und Lizenzhinweis in Fußzeile, Info-Dialog und Logo-Hinweis. Überschreibt die Texte aus strings.py
(spätere Textdateien gewinnen). Der Name steht nur hier und in den Dokumenten."""
from __future__ import annotations

from .strings import TEXTS

AUTHOR = "conejito-vipe"

TEXTS["de"].update({
    "footer.before": f"vibecoded with Claude (Anthropic) by {AUTHOR} with love",
    "about.text": "Claudios {version}\nWebsite Checks, SEO & Diagnostics\n\n"
                  f"Freeware · vibecoded with Claude (Anthropic) by {AUTHOR} with love ♥\n"
                  "{lines} Zeilen Python\n\n"
                  "Keine Gewährleistung und Haftung, soweit gesetzlich zulässig.\n"
                  "Nur für eigene oder ausdrücklich freigegebene Websites. Ergebnisse sind technische "
                  "Indizien, keine Rechtsberatung.\n\nProjekt: {repo}",
    "about.licenses": f"Code: © {AUTHOR}, quelloffene Lizenz mit Einschränkungen: keine kommerzielle Nutzung, "
                      "keine Veränderung, keine Weitergabe (siehe LICENSE.de.txt).\n"
                      f"Logo: © {AUTHOR}, mit KI-Unterstützung erstellt, Nutzung nur zusammen mit Claudios.\n"
                      "Bibliotheken von Dritten behalten ihre eigenen Lizenzen: httpx (BSD-3), Beautiful Soup (MIT), "
                      "dnspython (ISC), publicsuffix2 (MIT/MPL-2.0), PySide6 (LGPL-3.0), openpyxl (MIT).\n"
                      "Quellen und Details: THIRD_PARTY_NOTICES.de.md und assets/ASSETS.de.md im Repository.",
})
TEXTS["en"].update({
    "footer.before": f"vibecoded with Claude (Anthropic) by {AUTHOR} with love",
    "about.text": "Claudios {version}\nWebsite Checks, SEO & Diagnostics\n\n"
                  f"Freeware · vibecoded with Claude (Anthropic) by {AUTHOR} with love ♥\n"
                  "{lines} lines of Python\n\n"
                  "No warranty and no liability, as far as legally permitted.\n"
                  "Only for your own or explicitly authorised websites. Results are technical "
                  "indications, not legal advice.\n\nProject: {repo}",
    "about.licenses": f"Code: © {AUTHOR}, source-available licence with restrictions: no commercial use, "
                      "no modification, no distribution (see LICENSE).\n"
                      f"Logo: © {AUTHOR}, created with AI assistance, use only together with Claudios.\n"
                      "Third-party libraries keep their own licences: httpx (BSD-3), Beautiful Soup (MIT), "
                      "dnspython (ISC), publicsuffix2 (MIT/MPL-2.0), PySide6 (LGPL-3.0), openpyxl (MIT).\n"
                      "Sources and details: THIRD_PARTY_NOTICES.md and assets/ASSETS.md in the repository.",
})
