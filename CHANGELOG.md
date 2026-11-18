# Changelog

Deutsche Fassung: [CHANGELOG.de.md](CHANGELOG.de.md)

## 0.1.0 (unreleased)

- **Core:** HTTPS-only gatekeeper with DoH and IP pinning, crawler (6 levels), fixed limits, tamper-evident scan log with a control value, reports.
- **Checks:** HTML, accessibility and forms, security headers and cookies, `security.txt`, DNS and mail security (including the MTA-STS policy file), links, takeover hints and fingerprints, ads.txt, CORS, cache control, privacy and consent banner quality, SEO (including robots.txt in depth, structured data in depth, URL structure, click depth, thin content, favicon, local SEO, shops, international SEO), AI crawlers and `llms.txt`, TLS certificate.
- **Tool checks:** W3C Nu Html Checker, W3C CSS Validator, ESLint, Stylelint, retire.js, sslyze (protocols, ciphers, level-2 attack tests), Chromium checks with axe-core, optional Firefox and WebKit comparison, passive OWASP ZAP (level 2).
- **Level 2:** Google sign-in (read access), live property check before every scan, proof valid for one host, 15 minutes and one use, Search Console data, fixed path list, 10 scans per domain and day.
- **Abuse protection:** stricter input rules, total time budget and minimum pause for browser, ZAP and sslyze, DNS rebinding detection, discarding of data of third-party hosts with non-public addresses.
- **Windows GUI (DE/EN):** scan page with level display, findings page with filters and details, export page (CSV, Excel, PDF, ZIP with focus prompts), optional history with comparison, page "External services", component manager with checksums, removal with selection, Inno Setup installer.
- **Optional services (off by default):** RDAP domain expiry, Google Safe Browsing (own key), PageSpeed Insights; local screenshots.
- **Windows build:** PyInstaller folder build and installer in CI; a pinned Python runtime for sslyze in the installed program (not yet verified on real machines).
