# Changelog

Deutsche Fassung: [CHANGELOG.de.md](CHANGELOG.de.md)

## 0.2.0 (unreleased)

- **GUI:** dark design (draft B): icon rail with labels and logo, new start screen, help with table of contents and shared search, score ring and category cards on the results page, explanation column next to the findings list.
- **Administration:** interface of CONEJITO (Admin): signed licence keys (`CL1`) and signed switch file (`SW1`, Ed25519, offline check, HTTPS GET only on button press). New page "Pro and licence", shipped inactive (no navigation entry, no locks, no prices) until the administration enables it. Public key, switch file address and the Pro switch are read only from a local file `verwaltung.json` in the data folder; licence data never belongs in the repository (`.gitignore`, repository test).

## 0.1.0 (unreleased)

- **Core:** HTTPS-only gatekeeper with DoH and IP pinning, crawler (6 levels), fixed limits, tamper-evident scan log with a control value, reports.
- **Checks:** HTML, accessibility and forms, security headers and cookies, `security.txt`, DNS and mail security (including the MTA-STS policy file), links, takeover hints and fingerprints, ads.txt, CORS, cache control, privacy and consent banner quality, SEO (including robots.txt in depth, structured data in depth, URL structure, click depth, thin content, favicon, local SEO, shops, international SEO), AI crawlers and `llms.txt`, TLS certificate.
- **Tool checks:** W3C Nu Html Checker, W3C CSS Validator, ESLint, Stylelint, retire.js, sslyze (protocols, ciphers, level-2 attack tests), Chromium checks with axe-core, optional Firefox and WebKit comparison, passive OWASP ZAP (level 2).
- **Level 2:** Google sign-in (read access), live property check before every scan, proof valid for one host, 15 minutes and one use, Search Console data, fixed path list, 12 scans per domain and day.
- **Abuse protection:** stricter input rules, total time budget and minimum pause for browser, ZAP and sslyze, DNS rebinding detection, discarding of data of third-party hosts with non-public addresses, 30 s cool-down with a countdown, 5 scans per domain and day at level 1.
- **Windows GUI (DE/EN):** scan page with level display, profile explanations, expert settings for external services (asked again before every scan) and scroll bar, findings page with filters and details, export page (CSV, Excel, PDF, ZIP with focus prompts), optional history with comparison, page "External services", component manager with checksums, removal with selection, Inno Setup installer.
- **Optional services (off by default):** RDAP domain expiry, Google Safe Browsing (own key), PageSpeed Insights (own key recommended); local screenshots.
- **Windows build:** PyInstaller folder build and installer in CI; a pinned Python runtime for sslyze in the installed program; explicit bundling of the modules that DNS over HTTPS needs. First test on Windows 10 done, fixes in progress.
