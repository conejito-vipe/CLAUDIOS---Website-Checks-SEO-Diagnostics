# Third-party notices / Lizenzen Dritter

Claudios itself is MIT-licensed. Components below are used under their own licences. The licence column is
written from memory: **verify it at the source before every release.** Entries marked "(verify)" are ones where I
am particularly unsure. Not legal advice.

Claudios is not affiliated with Google, the W3C, the OWASP ZAP project, Microsoft or any vendor named here.

## Python libraries (linked into Claudios)

| Component | Licence | Source |
|---|---|---|
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| Beautiful Soup 4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| dnspython | ISC | https://github.com/rthalley/dnspython |
| publicsuffix2 | MIT; the list itself MPL-2.0 | https://github.com/nexB/python-publicsuffix2 |
| Public Suffix List | MPL-2.0 | https://publicsuffix.org |
| PySide6 (Qt for Python) | LGPL-3.0 (the Windows build is a folder build so the library can be replaced) | https://www.qt.io/qt-for-python |

## Build tools (not part of the installed program)

| Component | Licence | Source |
|---|---|---|
| PyInstaller | GPL-2.0 with an exception that allows bundling (verify) | https://pyinstaller.org |
| Inno Setup | own free licence (verify) | https://jrsoftware.org/isinfo.php |

## Tools downloaded at setup (separate programs, never bundled in the repository)

| Component | Licence | Source |
|---|---|---|
| Eclipse Temurin JRE | GPL-2.0 with Classpath Exception | https://adoptium.net |
| Node.js | MIT | https://nodejs.org |
| W3C Nu Html Checker (vnu.jar) | MIT | https://github.com/validator/validator |
| W3C CSS Validator | W3C Software licence (verify) | https://github.com/w3c/css-validator |
| OWASP ZAP | Apache-2.0 | https://www.zaproxy.org |
| ESLint | MIT | https://eslint.org |
| eslint-plugin-security | Apache-2.0 (verify) | https://github.com/eslint-community/eslint-plugin-security |
| Stylelint | MIT | https://stylelint.io |
| retire.js | Apache-2.0 | https://retirejs.github.io/retire.js/ |
| sslyze | AGPL-3.0 | https://github.com/nabla-c0d3/sslyze |
| Playwright | Apache-2.0 | https://playwright.dev |
| axe-core | MPL-2.0 | https://github.com/dequelabs/axe-core |
| Chromium (downloaded by Playwright) | BSD-3-Clause and many bundled third-party licences (verify) | https://www.chromium.org |

All of these except sslyze, Chromium and the ZAP archive are pinned by checksum or by a lock file with integrity
hashes. **The Chromium download is fetched by Playwright from its own server over HTTPS and is not pinned by a
checksum of Claudios.**

**sslyze (AGPL-3.0):** Claudios never imports it. It is installed into its own isolated Python environment and
only started as an external process; its output is read as JSON. Whether this separation is sufficient for your
use is a legal question. If you distribute Claudios commercially, have it checked.

Not used yet: Lighthouse (Apache-2.0).

## Data sources

Public Suffix List (MPL-2.0). The vulnerability list used by retire.js is downloaded by retire.js itself from
raw.githubusercontent.com over HTTPS. Reference documents (W3C, WHATWG, OWASP, IETF RFCs, Google, IAB) are linked,
not copied.

## Logo and trademarks

The logo is © fuhfux, created with AI assistance, for use only together with Claudios. It shows depictions of the
HTML5, CSS3 and JavaScript badges; the source of those badges is still to be confirmed (see `assets/ASSETS.md`).
HTML5 logo: W3C, CC BY 3.0, https://www.w3.org/html/logo/. All product names belong to their owners.

## Nachtrag / Addendum (Lizenzen aus dem Gedächtnis, bitte prüfen / licenses from memory, please verify)
- Firefox (über Playwright, optionale Komponente „Firefox und WebKit“): MPL-2.0 (verify). Playwright lädt ihn von seinem eigenen Server, Claudios pinnt die Datei nicht.
- WebKit (über Playwright): LGPL-2.1 und BSD (verify).
- Python-Laufzeit (Python embeddable, nur im gebauten Windows-Programm): PSF-2.0 (verify). Adresse und SHA256 stehen in `components/runtime-lock.json`.
- pip (nur im gebauten Windows-Programm): MIT (verify).
- openpyxl und et_xmlfile (Excel-Export): MIT (verify).
