# Firefox, WebKit and the Python runtime

Deutsche Fassung: [ENGINES_AND_RUNTIME.de.md](ENGINES_AND_RUNTIME.de.md)

## Browser comparison (Firefox and WebKit)

- **When:** only in the deep profile and only with the component "Firefox and WebKit" (page Components).
- **What:** at most 3 pages, one run of `engine_probe.js`. It counts towards the tool budget (browser runs per scan: 4).
- **Rules:** as in the Chromium run: no HTTP, no local addresses, no service workers, certificate errors are never ignored.
- **Limit:** the target host is **not** pinned to the verified IP here (Chromium does that with `--host-resolver-rules`). Claudios checks the resolution before and after the run (`core/rebind.py`) and afterwards the observed third-party hosts (`core/foreign.py`, check `BRW-FRN-001`). A change in the middle of a run is detected, not prevented.
- **Downloads:** Playwright loads Firefox and WebKit from its own server over HTTPS. Claudios does not pin these files (as with Chromium).

## Python runtime for sslyze (built Windows program only)

- The program has no Python of its own. Therefore two components exist that appear only in the built program: `python-runtime` (Python embeddable) and `pip-wheel` (pip). Both are pinned with SHA256 in `components/runtime-lock.json`. The workflow "Laufzeit-Sperrdatei erzeugen" creates that file.
- sslyze is installed into a copy of the runtime (`pip --require-hashes --no-deps`, only from `pip-sslyze.json`).
- **Order:** first run the workflow "Laufzeit-Sperrdatei erzeugen", then the Windows build.
- **Unverified:** whether building sslyze from its source archive works in the embedded runtime. Until then the check TLS-PRO-001 counts as not executed, never as passed.
