# Security Policy

Deutsche Fassung: [SECURITY.de.md](SECURITY.de.md)

## Reporting a vulnerability

Use GitHub: **Security → Report a vulnerability** (private vulnerability reporting). Please do not open public issues for vulnerabilities and do not post secrets, tokens or personal data.

I cannot promise response times; this is a hobby project.

## What is in scope

- Bypassing the built-in limits or the level-2 verification by normal use of the program
- Leaking passwords, cookie values or tokens into reports, logs or exports
- Unsafe handling of downloaded tools (checksums, archive extraction)
- Injection through content of a checked website (reports, user interface)

## Honest limits

Claudios is open source. The abuse protections (limits, HTTPS only, verification levels, scan log) prevent accidental or convenient misuse. They cannot stop someone who modifies the code. Use Claudios only on systems you own or are authorised to test (compare § 202c StGB and the law of your country). No warranty. More: [THREAT_MODEL.md](THREAT_MODEL.md) and [docs/ABUSE_PROTECTION.md](docs/ABUSE_PROTECTION.md).

## Known gaps

- The Windows build and installer are not yet verified on real machines, nor are the Google sign-in and the control value of the scan log in the Windows Credential Manager.
- sslyze is built from its source archive (no wheel on PyPI); its build tools are not hash-checked.
- Browser, ZAP and sslyze open their own connections and do not use the throttling of Claudios. A total time budget and a minimum pause apply, and hosts they resolved themselves are re-checked afterwards (detected, not prevented).
- The browser downloads (Chromium, Firefox, WebKit) come from Playwright's server and are not pinned by a checksum of Claudios.
- The answer formats of Safe Browsing and PageSpeed (with a valid key) and the AI bot names are still unverified (see [docs/EXTERNAL_SERVICES.md](docs/EXTERNAL_SERVICES.md)).
- The installer and program are not code-signed; Windows SmartScreen may warn (see [FAQ](FAQ.md)).
