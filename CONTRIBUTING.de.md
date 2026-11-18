# Mitwirken

English version: [CONTRIBUTING.md](CONTRIBUTING.md)

Danke fürs Mitmachen.

## Einrichtung

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev,gui]"
    ruff check src tests tools
    pytest

## Regeln, die Tests erzwingen

- Kein `verify=False`, keine `http://`-Literale, keine Shell-Ausführung, keine Kommandozeilen-Schnittstelle
- Zahlen in der Oberfläche laufen über `format_number()` (DE `1.000`, EN `1,000`)
- Jede Prüfung hat „Warum“, Methode, Bewertungslogik, Behebung und https-Referenzen auf **Deutsch und Englisch**
- Jeder Fehlercode hat einen Katalogeintrag in beiden Sprachen
- Eine Prüfung, die nicht lief, ist „nicht ausgeführt“, nie „bestanden“
- Berichte und Exporte enthalten nie Passwörter, Cookie-Werte oder Tokens
- Jede Komponente steht in `THIRD_PARTY_NOTICES.md`

## Erweiterungspunkte (neue Datei, keine Änderung an bestehenden)

| Was | Wo |
|---|---|
| Prüfung | `src/claudios/checks/<name>.py` mit `@check(...)` (Dateien mit `_` am Anfang werden nicht geladen) |
| Probe (Zusatzdaten nach dem Crawl) | `src/claudios/core/probe_<name>.py` mit `NAME`, `MIN_LEVEL` und `async collect(gk, snap, resolver)` |
| Seite des Hauptfensters | `src/claudios/ui/page_<name>.py` mit `NAV_KEY` und `create(window)` |
| Oberflächentexte | `src/claudios/i18n/strings_<name>.py` |
| Fehlermeldungen | `src/claudios/i18n/errors_<name>.json` |
| Komponente | `src/claudios/components/extra_<name>.py` mit `COMPONENT` |

Ergänze einen Test mit einem guten und einem schlechten Beispiel. Feste Grenzen gehören nur in `core/limits.py`. Prüfungen werten nur den Snapshot aus; Anfragen laufen in Probes und immer über den Gatekeeper (`core/net.py`).

Dateien, die vorhanden sein müssen, stehen in `tools/manifests/<paket>.txt`; der Workflow „Autofix und Dateiprüfung“ liest sie. Sieh dir seine Annotationen auch bei einem grünen Lauf an.

## Dokumente

Jedes Dokument hat eine englische Hauptdatei und daneben eine deutsche `.de.md`-Datei. Eine Sprache pro Datei, keine gemischten Texte. Halte beide gleich.

## Bitte nicht

- Funktionen einbauen, die Massenscans, Skripting oder das Aufheben der Grenzen ermöglichen
- Geheimnisse, Client-Secrets, Tokens, Berichte oder Protokolle committen
- Werkzeuge ohne feste Version und Prüfsumme und ohne Eintrag in `THIRD_PARTY_NOTICES.md` hinzufügen
