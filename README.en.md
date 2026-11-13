# Claudios – Website Checks, SEO & Diagnostics

Freeware Windows tool (Python) that checks websites for clean HTML/CSS/JS (W3C references),
security, privacy, SEO and accessibility. Every check explains *why* it matters.

*vipecoded with Claude (Anthropic) by fuhfux with love ❤️ – not affiliated with Anthropic.*

## Safety by design
- HTTPS only; certificate errors abort the scan with a clear reason
- Max. 6 crawl levels, 25 pages (unverified) / 100 pages (verified), rate-limited
- One domain per scan; no CLI/API/batch mode, no plugins, no telemetry
- Passwords, cookie values and tokens are never stored or exported
- Active checks only for domains verified via Google Search Console

## Development
    py -3.12 -m venv .venv && .venv\Scripts\activate
    pip install -e .[dev]
    pytest

Use only on sites you own or are authorised to test. Findings are technical indications,
not legal advice. See SECURITY.md. No warranty.
