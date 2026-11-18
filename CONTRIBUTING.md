# Contributing

Deutsche Fassung: [CONTRIBUTING.de.md](CONTRIBUTING.de.md)

Thanks for helping.

## Setup

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev,gui]"
    ruff check src tests tools
    pytest

## Rules that tests enforce

- No `verify=False`, no `http://` literals, no shell execution, no command-line scan interface
- Numbers in the UI go through `format_number()` (DE `1.000`, EN `1,000`)
- Every check has a "why", method, rating logic, fix and https references in **German and English**
- Every error code has a catalog entry in both languages
- A check that did not run is "skipped", never "passed"
- Reports and exports never contain passwords, cookie values or tokens
- Every component appears in `THIRD_PARTY_NOTICES.md`

## Extension points (new file, no change to existing files)

| What | Where |
|---|---|
| Check | `src/claudios/checks/<name>.py` with `@check(...)` (files starting with `_` are not loaded) |
| Probe (extra data after the crawl) | `src/claudios/core/probe_<name>.py` with `NAME`, `MIN_LEVEL` and `async collect(gk, snap, resolver)` |
| Page of the main window | `src/claudios/ui/page_<name>.py` with `NAV_KEY` and `create(window)` |
| UI texts | `src/claudios/i18n/strings_<name>.py` |
| Error messages | `src/claudios/i18n/errors_<name>.json` |
| Component | `src/claudios/components/extra_<name>.py` with `COMPONENT` |

Add a test with a good and a bad example. Fixed limits belong in `core/limits.py`, nowhere else. Checks only evaluate the snapshot; requests happen in probes and always go through the gatekeeper (`core/net.py`).

New files that must exist are listed in `tools/manifests/<package>.txt`; the workflow "Autofix und Dateiprüfung" reads them. Look at its annotations even when the run is green.

## Documents

Every document has an English main file and a German `.de.md` file next to it. One language per file, no mixed texts. Keep both in sync.

## Please do not

- Add features that enable mass scanning, scripting or removing the limits
- Commit secrets, client secrets, tokens, reports or logs
- Add tools without a pinned version and checksum, and an entry in `THIRD_PARTY_NOTICES.md`
