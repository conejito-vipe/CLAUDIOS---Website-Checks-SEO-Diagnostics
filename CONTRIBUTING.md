# Feedback and development notes

Deutsche Fassung: [CONTRIBUTING.de.md](CONTRIBUTING.de.md)

Thanks for your interest. The [LICENSE](LICENSE) forbids modification and distribution, with one exception (section 3b): you may change the Software solely to send the author a suggested improvement. So **pull requests are welcome as suggestions**, and so are issues. Whether a suggestion is adopted is the author's decision.

## What helps

- **Bug reports and ideas:** open an issue (use the template "Bug report"). Include the error code (for example `CLA-TLS-001`) and, if you like, the last lines of `CLAUDIOS.log` without private addresses.
- **Suggested improvements:** open an issue or a pull request. By submitting it you grant the author the right described in section 3b of the LICENSE. Keep the change limited to the suggestion.
- **Security reports:** use **Security → Report a vulnerability**, see [SECURITY.md](SECURITY.md). No public issues for vulnerabilities.
- **Never post** passwords, tokens, cookie values or private URLs.

## Development notes (for the author)

The following notes document how the project is built. Others may build the unmodified program for their own use (see the licence) but not change it.

    py -3.12 -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev,gui]"
    ruff check src tests tools
    pytest

Rules that tests enforce:

- No `verify=False`, no `http://` literals, no shell execution, no command-line scan interface
- Numbers in the UI go through `format_number()` (DE `1.000`, EN `1,000`)
- Every check has a "why", method, rating logic, fix and https references in **German and English**
- Every error code has a catalog entry in both languages
- A check that did not run is "skipped", never "passed"
- Reports and exports never contain passwords, cookie values or tokens
- Every component appears in `THIRD_PARTY_NOTICES.md`

Extension points (new file, no change to existing files):

| What | Where |
|---|---|
| Check | `src/claudios/checks/<name>.py` with `@check(...)` (files starting with `_` are not loaded) |
| Probe (extra data after the crawl) | `src/claudios/core/probe_<name>.py` with `NAME`, `MIN_LEVEL` and `async collect(gk, snap, resolver)` |
| Page of the main window | `src/claudios/ui/page_<name>.py` with `NAV_KEY` and `create(window)` |
| UI texts | `src/claudios/i18n/strings_<name>.py` |
| Error messages | `src/claudios/i18n/errors_<name>.json` |
| Component | `src/claudios/components/extra_<name>.py` with `COMPONENT` |

Fixed limits belong in `core/limits.py`, nowhere else. Checks only evaluate the snapshot; requests happen in probes and always go through the gatekeeper (`core/net.py`). New files that must exist are listed in `tools/manifests/<package>.txt`; the workflow "Autofix und Dateiprüfung" reads them.

## Documents

Every document has an English main file and a German `.de.md` file next to it. One language per file, no mixed texts. Keep both in sync.
