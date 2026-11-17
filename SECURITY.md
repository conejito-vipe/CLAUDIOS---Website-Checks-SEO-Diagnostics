# Security Policy / Sicherheitsrichtlinie

## Reporting a vulnerability / Schwachstelle melden

Use GitHub: **Security → Report a vulnerability** (private vulnerability reporting). Please do not open public
issues for vulnerabilities and do not post secrets, tokens or personal data.
Nutze GitHub: **Security → Report a vulnerability** (private Meldung). Bitte keine öffentlichen Issues für
Schwachstellen und keine Geheimnisse, Tokens oder personenbezogene Daten posten.

(The repository owner must enable "Private vulnerability reporting" under Settings → Code security.)

I cannot promise response times; this is a hobby project.

## What is in scope / Was zählt

- Bypassing the built-in limits or the level-2 verification by normal use of the program
- Leaking passwords, cookie values or tokens into reports, logs or exports
- Unsafe handling of downloaded tools (checksums, archive extraction)
- Injection through content of a checked website (reports, user interface)

## Honest limits / Ehrliche Grenzen

Claudios is open source. The abuse protections (limits, HTTPS only, verification levels) prevent accidental or
convenient misuse. They cannot stop someone who modifies the code. Use Claudios only on systems you own or are
authorised to test (compare § 202c StGB and the law of your country). No warranty.

Claudios ist Open Source. Die Schutzmaßnahmen verhindern versehentlichen oder bequemen Missbrauch, nicht
entschlossene Änderungen am Code. Nur für eigene oder ausdrücklich freigegebene Systeme verwenden.

## Known gaps / Bekannte Lücken

- Windows build and installer are not yet verified on real machines.
- sslyze is built from its source archive (no wheel on PyPI); its build tools are not hash-checked.
- External tools (sslyze, retire.js) open their own connections and do not use Claudios' throttling.
- The installer and program are not code-signed; Windows SmartScreen may warn (see FAQ).
