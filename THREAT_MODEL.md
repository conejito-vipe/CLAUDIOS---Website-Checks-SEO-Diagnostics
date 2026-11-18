# Threat model

Deutsche Fassung: [THREAT_MODEL.de.md](THREAT_MODEL.de.md)

Status: after packages 6f to 6n. This document describes what Claudios protects, against whom and where the limits are. The measures are backed by tests (`tests/test_policy.py`, `tests/test_security_policy.py`, `tests/test_hostile_input.py`, `tests/test_abuse_protection.py` and others), but so far only against simulated data. The protective layers are listed in [docs/ABUSE_PROTECTION.md](docs/ABUSE_PROTECTION.md), services at third parties in [docs/EXTERNAL_SERVICES.md](docs/EXTERNAL_SERVICES.md).

## Assets

| Asset | Why it matters |
|---|---|
| Third-party servers | They must not be attacked, overloaded or probed. |
| Secrets of the user | Google token, client secret, API keys for Safe Browsing and PageSpeed. Passwords and cookie values are never stored. |
| The user's computer | Downloaded tools execute code. |
| Integrity of reports | Checks that did not run must never appear as passed. |

## Actors

| Actor | Goal | Measures |
|---|---|---|
| **Abuser** (user who wants to check foreign or many sites) | Mass or foreign scans, active tests without permission | One domain per scan, depth 6, 25 or 100 pages, throttling, cool-down, hourly and daily limits, tamper-evident scan log, HTTPS only, no private addresses, no command line, no plugin system. Active checks only at level 2 (Search Console, owner or full access, re-checked live before every scan, proof valid for one host, 15 minutes and one use). |
| **Hostile website** | Block the program, poison reports, attack the computer | All patterns run in linear time, size and time limits, escaping of all content in the interface and in the HTML report (CSP), tools get files and never addresses, browsers with blocked service workers and requests only over HTTPS to public names. |
| **Supply chain** (manipulated download or package) | Malicious code through tools | Fixed versions with SHA256 or lock file, safe extraction (no zip slip, no symlinks, size limit), `npm ci --ignore-scripts`, `pip --require-hashes --no-deps`, only actions from GitHub itself in the workflows. The workflow "Sicherheitsprüfung" checks the fixed versions for known vulnerabilities. |
| **Other program on the computer** | Steal tokens | Tokens only in memory or in the Windows Credential Manager, never in files, logs or ZIPs. Redaction on input and before export. |

## Deliberately not protected

- **Anyone who changes the source code.** Claudios is open source. The limits are friction against convenience, not protection against the determined.
- **An attacker with administrator rights** on the user's computer.
- **A hijacked account** at Google, npm, PyPI or GitHub.
- **The browser downloads** (Chromium, Firefox, WebKit) from Playwright: they come from its server over HTTPS and are not secured by a checksum of Claudios.
- **Unsigned program file:** Windows SmartScreen may warn.

## Residual risks

- **Third-party hosts are detected, not prevented.** Chromium, Firefox, WebKit and ZAP resolve the names of third-party hosts themselves. If a name points to a non-public address the access has already happened. Claudios resolves every observed host again via DoH afterwards, discards its data and reports it (`BRW-FRN-001`).
- **The target host is not pinned to the verified IP in the ZAP run and in the Firefox/WebKit run** (Chromium is pinned). There the resolution is only checked before and after the run (`core/rebind.py`).
- **Browser, ZAP and sslyze connect directly** and do not know the throttling of the gatekeeper. A total time budget (1,800 s), a minimum pause (15 s) and a maximum number of runs apply per scan. The runtime of the ZAP daemon itself is not counted, only the browser script through ZAP.
- **The control value of the scan log is friction, not protection.** Whoever deletes log and control value looks like a fresh installation. Writing the control value to the Windows Credential Manager is not yet verified on real machines.
- **The level-2 proof lives in memory.** Whoever changes the source code can forge it.
- **Safe Browsing and PageSpeed resolve names through the system**, not through DoH. The targets are two fixed Google hosts, without redirects and with a size limit.
- **Screenshots show page content.** They stay local and are only saved as a ZIP on request, but they are not checked for secrets.
- **PageSpeed lets Google fetch the page.** That is a normal page view by a third party, only on explicit request.
- **Workflows reference actions by version tag**, not by commit checksum. Dependabot keeps them current.
- **sslyze (AGPL-3.0) is built from the source archive**, and its build tools are not secured by a checksum.
- **sslyze runs with a newer `cryptography` than it allows itself.** The workflow "pip-Sperrliste" forces it because the version allowed by the package has known vulnerabilities, and accepts it only after a successful sslyze run against a real site. That does not prove that every certificate is processed correctly. An error would show as "not executed", never as "passed".
- **The git history is not searched for secrets automatically**, only the current state.
- **Findings contain text from foreign websites.** CSV and Excel exports neutralise formula injection; the PDF and HTML reports escape everything.
- **Some formats are still unverified:** the answer format of Safe Browsing and PageSpeed with a valid key, the licence entries marked "(verify)" and everything on Windows. Verified on a GitHub runner (Linux): the ZAP interface `core/view/hosts`, the RDAP format, all eight fingerprint texts, the 14 original AI bot names (against ai.robots.txt), the scripts `shot_probe.js` and `engine_probe.js` with real Chromium, Firefox and WebKit, and ESLint 9, Stylelint 16 and retire.js 6 with the Claudios configurations.

## Routine checks

The workflow "Sicherheitsprüfung" (`.github/workflows/security.yml`) runs by hand and weekly: bandit for the Python code, pip-audit and npm audit for the dependencies, and it creates a bill of materials (SBOM). Messages appear as annotations in the run.
