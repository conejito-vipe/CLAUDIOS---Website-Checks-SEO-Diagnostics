# Contributing / Mitwirken

Thanks for helping. / Danke fürs Mitmachen.

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
- Reports never contain passwords, cookie values or tokens

## Adding a check

Create one new file in `src/claudios/checks/`. It is loaded automatically. Use the `@check(...)` decorator (see an
existing file such as `ads.py`) and add a test with a good and a bad example. Texts for the UI go into a new
`src/claudios/i18n/strings_<name>.py`, error messages into a new `errors_<name>.json`.

## Please do not

- Add features that enable mass scanning, scripting or removing the limits
- Commit secrets, client secrets, tokens, reports or logs
- Add tools without a pinned version and checksum, and an entry in `THIRD_PARTY_NOTICES.md`
