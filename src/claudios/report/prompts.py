"""Prompt-Vorlagen je Schwerpunkt (DE/EN). 'general' ist der bisherige Prompt aus report.py. Die Präfixe sind
Hinweise auf Prüfungs-IDs; sie bestimmen auch, welche Befunde in summary.md der Schwerpunkt-ZIP stehen."""
from __future__ import annotations

from .report import PROMPT

FOCI = ("general", "security", "seo", "privacy", "accessibility", "code")

PREFIXES = {
    "general": (),
    "security": ("SEC-", "TLS-", "EXP-", "ZAP-", "TKO-", "DNS-"),
    "seo": ("SEO-", "GSC-", "HTM-HDG", "HTM-IMG", "BRW-PRF"),
    "privacy": ("PRV-", "ADS-", "SEC-COK", "SEC-EML", "SEC-PPL", "BRW-FRN"),
    "accessibility": ("BRW-AXE", "BRW-RSP", "HTM-IMG", "HTM-HDG", "HTM-LND", "HTM-FRM", "HTM-IDS", "HTM-STR"),
    "code": ("HTM-",),
}

TEXT = {
    "de": {
        "security": ("Sicherheit",
                     "Achte besonders auf Header (CSP, HSTS, Cookies), TLS, offene Pfade, Geheimnisse im Quelltext, "
                     "DNS- und E-Mail-Schutz (SPF, DKIM, DMARC) und Subdomain-Takeover. Ordne die Funde nach "
                     "Ausnutzbarkeit."),
        "seo": ("SEO",
                "Achte auf Indexierbarkeit (noindex, robots.txt, Sitemap, Canonical), Titel und Beschreibungen, "
                "Überschriften, strukturierte Daten, hreflang, Ladeleistung und URL-Struktur. Ordne nach dem "
                "erwarteten Effekt auf die Sichtbarkeit."),
        "privacy": ("Datenschutz",
                    "Achte auf Tracker, Fremddienste, Cookies vor der Einwilligung, die Einwilligungslösung, Links "
                    "zu Impressum und Datenschutzerklärung und E-Mail-Adressen im Klartext. Das sind technische "
                    "Indizien, keine Rechtsberatung; nenne, was eine juristische Prüfung klären sollte."),
        "accessibility": ("Barrierefreiheit",
                          "Achte auf Funde von axe-core (WCAG 2.2), Alternativtexte, Überschriftenstruktur, "
                          "Landmarks, Formularbeschriftungen und das Verhalten bei schmalen Fenstern. Nenne zu jedem "
                          "Fund das betroffene WCAG-Kriterium, soweit du sicher bist."),
        "code": ("Code-Qualität",
                 "Achte auf gültiges HTML, CSS- und JavaScript-Fehler, Funde der Linter, veraltete Bibliotheken und "
                 "Konsolenfehler im Browser. Gib Korrekturen als Code an."),
    },
    "en": {
        "security": ("security",
                     "Pay special attention to headers (CSP, HSTS, cookies), TLS, exposed paths, secrets in the "
                     "source code, DNS and e-mail protection (SPF, DKIM, DMARC) and subdomain takeover. Order the "
                     "findings by exploitability."),
        "seo": ("SEO",
                "Pay attention to indexability (noindex, robots.txt, sitemap, canonical), titles and descriptions, "
                "headings, structured data, hreflang, loading performance and URL structure. Order by the expected "
                "effect on visibility."),
        "privacy": ("privacy",
                    "Pay attention to trackers, third-party services, cookies before consent, the consent solution, "
                    "links to the legal notice and privacy policy and e-mail addresses in plain text. These are "
                    "technical indications, not legal advice; say what a legal review should clarify."),
        "accessibility": ("accessibility",
                          "Pay attention to axe-core findings (WCAG 2.2), alternative texts, heading structure, "
                          "landmarks, form labels and behaviour in narrow windows. For each finding name the "
                          "affected WCAG criterion as far as you are sure."),
        "code": ("code quality",
                 "Pay attention to valid HTML, CSS and JavaScript errors, linter findings, outdated libraries and "
                 "console errors in the browser. Give fixes as code."),
    },
}

_DE = """# Auftrag an Claude: Schwerpunkt {name}
Anbei der Prüfbericht des Tools **Claudios** (Website-Checks) als ZIP. Bitte konzentriere dich auf den Schwerpunkt **{name}**.
Relevant sind Befunde, deren Prüfungs-ID mit diesen Präfixen beginnt: {prefixes}. Andere Befunde nur erwähnen, wenn sie das Thema berühren.

{guidance}

Gehe so vor:
1. **Bewerte** den Zustand der Website im Schwerpunkt {name}.
2. **Priorisiere** die Befunde (kritisch zuerst) und erkläre je Befund kurz, warum er wichtig ist.
3. Gib **konkrete Lösungsvorschläge mit Codebeispielen**.
4. Nenne mögliche **Fehlalarme** und was Claudios nicht prüfen konnte (siehe `checks[].status` und `scan.status`). Nicht ausgeführte Prüfungen gelten nie als bestanden.
5. Fasse am Ende einen **Maßnahmenplan** zusammen (Quick Wins, mittelfristig).

Hinweise: Die Berichte enthalten keine Passwörter, Cookie-Werte oder Tokens. Zahlen in `report.html` und `summary.md` sind deutsch formatiert (**Punkt = Tausendertrenner**, Komma = Dezimal); in `report.json` stehen reine Zahlen. `summary.md` zeigt nur die Befunde des Schwerpunkts, `report.json` enthält alle.
Befunde sind technische Indizien, keine Rechtsberatung. Antworte auf Deutsch.
"""

_EN = """# Task for Claude: focus on {name}
Attached is the report of the tool **Claudios** (website checks) as a ZIP. Please concentrate on **{name}**.
Relevant are findings whose check ID starts with these prefixes: {prefixes}. Mention other findings only if they touch the topic.

{guidance}

Proceed like this:
1. **Assess** the state of the website regarding {name}.
2. **Prioritise** the findings (critical first) and briefly explain why each matters.
3. Provide **concrete fixes with code examples**.
4. Point out possible **false positives** and what Claudios could not check (see `checks[].status` and `scan.status`). Checks that did not run never count as passed.
5. Finish with an **action plan** (quick wins, medium term).

Notes: The reports contain no passwords, cookie values or tokens. Numbers in `report.html` and `summary.md` use English formatting (**comma = thousands separator**, period = decimal); `report.json` contains plain numbers. `summary.md` shows only the findings of the focus, `report.json` contains all of them.
Findings are technical indications, not legal advice. Answer in English.
"""


def prompt_for(focus: str, lang: str) -> str:
    if focus not in FOCI:
        raise ValueError("unknown focus")
    if focus == "general":
        return PROMPT[lang]
    name, guidance = TEXT[lang][focus]
    template = _DE if lang == "de" else _EN
    return template.format(name=name, prefixes=", ".join(PREFIXES[focus]), guidance=guidance)
