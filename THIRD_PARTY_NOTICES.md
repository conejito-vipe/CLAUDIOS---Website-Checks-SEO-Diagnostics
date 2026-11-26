# Third-party notices

Deutsche Fassung: [THIRD_PARTY_NOTICES.de.md](THIRD_PARTY_NOTICES.de.md)

CLAUDIOS itself is under the CLAUDIOS source-available licence (see [LICENSE](LICENSE): no commercial use, no modification, no distribution). The components below are used under their own licences, which the CLAUDIOS licence does not change. Entries without "(verify)" were compared with the licence metadata of PyPI, the npm registry and GitHub. Entries marked "(verify)" could not be confirmed that way: **verify them at the source before every release.** Not legal advice.

CLAUDIOS is not affiliated with Google, the W3C, the OWASP ZAP project, Microsoft or any vendor named here.

## Python libraries (linked into CLAUDIOS)

| Component | Licence | Source |
|---|---|---|
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| cryptography | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| Beautiful Soup 4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| dnspython | ISC | https://github.com/rthalley/dnspython |
| publicsuffix2 | MIT; the list itself MPL-2.0 | https://github.com/nexB/python-publicsuffix2 |
| Public Suffix List | MPL-2.0 | https://publicsuffix.org |
| PySide6 (Qt for Python) | dual-licensed (LGPL-3.0, GPL-2.0 or GPL-3.0), used under LGPL-3.0 (the Windows build is a folder build so the library can be replaced) | https://www.qt.io/qt-for-python |
| openpyxl (Excel export) | MIT | https://openpyxl.readthedocs.io/ |
| et_xmlfile (used by openpyxl) | MIT | https://pypi.org/project/et-xmlfile/ |

## Build tools (not part of the installed program)

| Component | Licence | Source |
|---|---|---|
| PyInstaller | GPL-2.0-or-later with a special exception that allows bundling | https://pyinstaller.org |
| Inno Setup | own free licence (verify) | https://jrsoftware.org/isinfo.php |
| Pillow (only used to create the program icon in the build) | HPND (verify) | https://python-pillow.org |

## Tools downloaded at setup (separate programs, never bundled in the repository)

| Component | Licence | Source |
|---|---|---|
| Eclipse Temurin JRE | GPL-2.0 with Classpath Exception | https://adoptium.net |
| Node.js | MIT | https://nodejs.org |
| W3C Nu Html Checker (vnu.jar) | MIT | https://github.com/validator/validator |
| W3C CSS Validator | W3C Software licence (verify) | https://github.com/w3c/css-validator |
| OWASP ZAP | Apache-2.0 | https://www.zaproxy.org |
| ESLint | MIT | https://eslint.org |
| eslint-plugin-security | Apache-2.0 | https://github.com/eslint-community/eslint-plugin-security |
| Stylelint | MIT | https://stylelint.io |
| retire.js | Apache-2.0 | https://retirejs.github.io/retire.js/ |
| sslyze | AGPL-3.0 | https://github.com/nabla-c0d3/sslyze |
| Playwright | Apache-2.0 | https://playwright.dev |
| axe-core | MPL-2.0 | https://github.com/dequelabs/axe-core |
| Chromium (downloaded by Playwright) | BSD-3-Clause and many bundled third-party licences (verify) | https://www.chromium.org |
| Firefox (downloaded by Playwright, optional component) | MPL-2.0 (verify) | https://www.mozilla.org/firefox/ |
| WebKit (downloaded by Playwright, optional component) | LGPL-2.1 and BSD (verify) | https://webkit.org |
| Python embeddable runtime (built Windows program only) | PSF-2.0 (verify) | https://www.python.org |
| pip (built Windows program only) | MIT | https://pip.pypa.io |

All of these except the browsers are pinned by a checksum or by a lock file with integrity hashes (the Python runtime and pip in `components/runtime-lock.json`). **The browser downloads (Chromium, Firefox, WebKit) are fetched by Playwright from its own server over HTTPS and are not pinned by a checksum of CLAUDIOS.**

**sslyze (AGPL-3.0):** CLAUDIOS never imports it. It is installed into its own isolated Python environment and only started as an external process; its output is read as JSON. Whether this separation is sufficient for your use is a legal question. The CLAUDIOS licence forbids commercial use and distribution by others, so only the author distributes the installer; if that changes, have this checked.

**Qt (LGPL-3.0):** The Windows build is a folder build, so the Qt libraries can be replaced. The CLAUDIOS licence does not restrict the rights that the LGPL gives you (section 7 of the licence).

Lighthouse (Apache-2.0) is not installed. Lighthouse results are only obtained, if you switch it on, through Google's PageSpeed Insights service.

## Optional online services (all off by default)

These services receive data only after you switch them on in the expert settings of the scan page or on the page "External services". Details: `docs/EXTERNAL_SERVICES.md`.

| Service | Operator | What is sent |
|---|---|---|
| RDAP (domain expiry) | IANA and the registry of the top-level domain | the registrable domain |
| Safe Browsing | Google | up to 5 addresses of the checked website, with your own API key |
| PageSpeed Insights | Google | the address of the home page, with your own API key if you stored one |

## Data sources

Public Suffix List (MPL-2.0). The vulnerability list used by retire.js is downloaded by retire.js itself from raw.githubusercontent.com over HTTPS. Reference documents (W3C, WHATWG, OWASP, IETF RFCs, Google, IAB) are linked, not copied. The fingerprint texts for subdomain takeover follow the public list can-i-take-over-xyz, the names of AI crawlers the list ai.robots.txt.

## Logo and trademarks

The logo is © conejito-vipe, created with AI assistance, for use only together with CLAUDIOS. It shows depictions of the HTML5, CSS3 and JavaScript badges; the source of those badges is still to be confirmed (see `assets/ASSETS.md`). HTML5 logo: W3C, CC BY 3.0, https://www.w3.org/html/logo/. All product names belong to their owners.
