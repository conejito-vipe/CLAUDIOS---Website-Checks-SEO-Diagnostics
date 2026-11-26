# Changelog

Deutsche Fassung: [CHANGELOG.de.md](CHANGELOG.de.md)

## 1.1.0 (unreleased)

- **New checks (passive):** address variants (http, www; `SEO-VAR-001`), sitemap compared with the crawl (`SEO-SMX-001`), images (`HTM-IMG-002`), caching and compression of CSS/JS (`SEO-ACH-001`), HTTP protocol and response time (`SEO-HTV-001`), HSTS preload and certificate names (`TLS-EXT-001`), keyboard operation and motion (`HTM-KEY-001`), page weight and blocking scripts (`SEO-WGT-001`), accessibility statement (`PRV-BFS-001`), Global Privacy Control (`PRV-GPC-001`), BIMI (`DNS-BIM-001`), DANE/TLSA (`DNS-DAN-001`), expiry of the domains of third-party scripts (`SEC-SUP-001`, only with the RDAP switch).
- **New opt-in service:** certificate logs via crt.sh (`SEC-CTL-001`, switch on the External services page, default off, only the registrable domain is sent).
- **New check (active, level 2):** CMS extra paths for WordPress and Joomla (`SEC-CMX-001`), in its own probe `probe_cms` and in the reviewed list of active checks.
- **Gatekeeper:** one plain http request without following redirects (only for the own domain, to test the http variant) and the single request header `Sec-GPC`; everything else stays refused.
- **Mac:** download-based tools run on the Mac (see 1.0.0).

## 1.0.0 (unreleased)

- **GUI:** dark design (draft B): icon rail with labels and logo, new start screen, help with table of contents and shared search, score ring and category cards on the results page, explanation column next to the findings list.
- **Administration:** interface of CONEJITO (Admin): signed licence keys (`CL1`) and signed switch file (`SW1`, Ed25519, offline check, HTTPS GET only on button press). New page "Pro and licence", shipped inactive (no navigation entry, no locks, no prices) until the administration enables it. Public key, switch file address and the Pro switch are read only from a local file `verwaltung.json` in the data folder; licence data never belongs in the repository (`.gitignore`, repository test).
- **macOS:** CLAUDIOS runs on the Mac (Apple silicon): data in `~/Library/Application Support/CLAUDIOS`, API keys in the Keychain (Security framework, no command line), Mac fonts, update check opens the release page, uninstall hint for the app. The release workflow builds `CLAUDIOS.app` (ad-hoc signed), runs the self-test on it and publishes `CLAUDIOS_v<version>_Mac.zip` with checksum; CI tests run on Linux, Windows and macOS. The download-based tools (Java, Node, validators, ZAP, ESLint/Stylelint/retire.js, Playwright) are set up on the Mac as well: the lock file has per-system variants with checksums, tar.gz archives are unpacked safely (links only inside the target, run permission kept), and the release run installs and starts every tool on a Mac. sslyze runs there in its own copy of Python (python-build-standalone, checksum from the lock file).
- **Self-test:** `CLAUDIOS.exe --selftest` writes a JSON status report (all modules importable, bundled files, DNS over HTTPS, check registry, writable data folder, real round trip through the Windows credential store, main window drawn). The Windows build runs it on the built and on the silently installed program, then uninstalls, and uploads the reports.
- **Security:** browser scripts now block local and internal names (`localhost.`, `*.localhost`, `*.lan`, `*.home.arpa`, single-label hosts) and any host whose DNS answer is private (router, NAS, cloud metadata address) in all four scripts alike; the ZAP API key is passed in a private file instead of on the command line; screenshots are deleted from disk when the DNS answer changed during the run.
- **Installer and CI:** update, repair and downgrade dialog like CLAUDIA (never in silent updates), old program files removed on update; actions pinned to commit hashes; release workflow runs the tests first and publishes checksums; CI on Linux and Windows; weekly security check with Gitleaks over the whole history.

## 0.1.0 (unreleased)

- **Core:** HTTPS-only gatekeeper with DoH and IP pinning, crawler (6 levels), fixed limits, tamper-evident scan log with a control value, reports.
- **Checks:** HTML, accessibility and forms, security headers and cookies, `security.txt`, DNS and mail security (including the MTA-STS policy file), links, takeover hints and fingerprints, ads.txt, CORS, cache control, privacy and consent banner quality, SEO (including robots.txt in depth, structured data in depth, URL structure, click depth, thin content, favicon, local SEO, shops, international SEO), AI crawlers and `llms.txt`, TLS certificate.
- **Tool checks:** W3C Nu Html Checker, W3C CSS Validator, ESLint, Stylelint, retire.js, sslyze (protocols, ciphers, level-2 attack tests), Chromium checks with axe-core, optional Firefox and WebKit comparison, passive OWASP ZAP (level 2).
- **Level 2:** Google sign-in (read access), live property check before every scan, proof valid for one host, 15 minutes and one use, Search Console data, fixed path list, 12 scans per domain and day.
- **Abuse protection:** stricter input rules, total time budget and minimum pause for browser, ZAP and sslyze, DNS rebinding detection, discarding of data of third-party hosts with non-public addresses, 30 s cool-down with a countdown, 5 scans per domain and day at level 1.
- **Windows GUI (DE/EN):** scan page with level display, profile explanations, expert settings for external services (asked again before every scan) and scroll bar, findings page with filters and details, export page (CSV, Excel, PDF, ZIP with focus prompts), optional history with comparison, page "External services", component manager with checksums, removal with selection, Inno Setup installer.
- **Optional services (off by default):** RDAP domain expiry, Google Safe Browsing (own key), PageSpeed Insights (own key recommended); local screenshots.
- **Windows build:** PyInstaller folder build and installer in CI; a pinned Python runtime for sslyze in the installed program; explicit bundling of the modules that DNS over HTTPS needs. First test on Windows 10 done, fixes in progress.
