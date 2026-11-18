# Hinweise zu Software Dritter

English version: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

Claudios selbst steht unter der MIT-Lizenz. Die folgenden Komponenten werden unter ihren eigenen Lizenzen verwendet. Einträge ohne „(verify)“ wurden mit den Lizenzangaben von PyPI, der npm-Registry und GitHub abgeglichen (Workflow „Praxisprüfung 2“). Einträge mit „(verify)“ ließen sich so nicht bestätigen: **Vor jeder Veröffentlichung an der Quelle prüfen.** Keine Rechtsberatung.

Claudios ist nicht mit Google, dem W3C, dem OWASP-ZAP-Projekt, Microsoft oder einem hier genannten Anbieter verbunden.

## Python-Bibliotheken (in Claudios eingebunden)

| Komponente | Lizenz | Quelle |
|---|---|---|
| httpx | BSD-3-Clause | https://github.com/encode/httpx |
| Beautiful Soup 4 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| dnspython | ISC | https://github.com/rthalley/dnspython |
| publicsuffix2 | MIT; die Liste selbst MPL-2.0 | https://github.com/nexB/python-publicsuffix2 |
| Public Suffix List | MPL-2.0 | https://publicsuffix.org |
| PySide6 (Qt for Python) | mehrfach lizenziert (LGPL-3.0, GPL-2.0 oder GPL-3.0), verwendet unter LGPL-3.0 (der Windows-Build ist ein Ordner-Build, die Bibliothek lässt sich ersetzen) | https://www.qt.io/qt-for-python |
| openpyxl (Excel-Export) | MIT | https://openpyxl.readthedocs.io/ |
| et_xmlfile (von openpyxl genutzt) | MIT | https://pypi.org/project/et-xmlfile/ |

## Bauwerkzeuge (nicht Teil des installierten Programms)

| Komponente | Lizenz | Quelle |
|---|---|---|
| PyInstaller | GPL-2.0-or-later mit einer Ausnahme, die das Bündeln erlaubt | https://pyinstaller.org |
| Inno Setup | eigene freie Lizenz (verify) | https://jrsoftware.org/isinfo.php |

## Werkzeuge, die bei der Einrichtung geladen werden (eigene Programme, nie im Repository enthalten)

| Komponente | Lizenz | Quelle |
|---|---|---|
| Eclipse Temurin JRE | GPL-2.0 mit Classpath Exception | https://adoptium.net |
| Node.js | MIT | https://nodejs.org |
| W3C Nu Html Checker (vnu.jar) | MIT | https://github.com/validator/validator |
| W3C CSS Validator | W3C-Software-Lizenz (verify) | https://github.com/w3c/css-validator |
| OWASP ZAP | Apache-2.0 | https://www.zaproxy.org |
| ESLint | MIT | https://eslint.org |
| eslint-plugin-security | Apache-2.0 | https://github.com/eslint-community/eslint-plugin-security |
| Stylelint | MIT | https://stylelint.io |
| retire.js | Apache-2.0 | https://retirejs.github.io/retire.js/ |
| sslyze | AGPL-3.0 | https://github.com/nabla-c0d3/sslyze |
| Playwright | Apache-2.0 | https://playwright.dev |
| axe-core | MPL-2.0 | https://github.com/dequelabs/axe-core |
| Chromium (von Playwright geladen) | BSD-3-Clause und viele eingebundene Lizenzen Dritter (verify) | https://www.chromium.org |
| Firefox (von Playwright geladen, optionale Komponente) | MPL-2.0 (verify) | https://www.mozilla.org/firefox/ |
| WebKit (von Playwright geladen, optionale Komponente) | LGPL-2.1 und BSD (verify) | https://webkit.org |
| Python-Laufzeit (embeddable, nur im gebauten Windows-Programm) | PSF-2.0 (verify) | https://www.python.org |
| pip (nur im gebauten Windows-Programm) | MIT | https://pip.pypa.io |

Alle diese Komponenten außer den Browsern sind per Prüfsumme oder per Sperrdatei mit Integritätsprüfsummen festgelegt (Python-Laufzeit und pip in `components/runtime-lock.json`). **Die Browser-Downloads (Chromium, Firefox, WebKit) lädt Playwright von seinem eigenen Server über HTTPS. Sie sind nicht durch eine Prüfsumme von Claudios festgelegt.**

**sslyze (AGPL-3.0):** Claudios importiert es nie. Es wird in einer eigenen, isolierten Python-Umgebung installiert und nur als externer Prozess gestartet, seine Ausgabe wird als JSON gelesen. Ob diese Trennung für deinen Einsatz genügt, ist eine Rechtsfrage. Bei kommerzieller Weitergabe von Claudios solltest du das prüfen lassen.

Lighthouse (Apache-2.0) wird nicht installiert. Lighthouse-Ergebnisse gibt es nur, wenn du es einschaltest, über den Dienst PageSpeed Insights von Google.

## Optionale Online-Dienste (alle standardmäßig aus)

Diese Dienste erhalten Daten erst, nachdem du sie auf der Seite „Externe Dienste“ eingeschaltet hast. Einzelheiten: `docs/EXTERNAL_SERVICES.md`.

| Dienst | Betreiber | Was gesendet wird |
|---|---|---|
| RDAP (Domainablauf) | IANA und die Registry der Domainendung | die registrierbare Domain |
| Safe Browsing | Google | bis zu 5 Adressen der geprüften Website, mit deinem eigenen API-Schlüssel |
| PageSpeed Insights | Google | die Adresse der Startseite, mit deinem eigenen API-Schlüssel, falls gespeichert |

## Datenquellen

Public Suffix List (MPL-2.0). Die Schwachstellenliste von retire.js lädt retire.js selbst von raw.githubusercontent.com über HTTPS. Referenzdokumente (W3C, WHATWG, OWASP, IETF-RFCs, Google, IAB) sind verlinkt, nicht kopiert. Die Fingerprint-Texte für Subdomain-Takeover folgen der öffentlichen Liste can-i-take-over-xyz, die Namen der KI-Crawler der Liste ai.robots.txt.

## Logo und Marken

Das Logo ist © fuhfux, mit KI-Unterstützung erstellt, nur zur Nutzung zusammen mit Claudios. Es zeigt Darstellungen der Zeichen für HTML5, CSS3 und JavaScript; die Quelle dieser Zeichen ist noch zu klären (siehe `assets/ASSETS.md`). HTML5-Logo: W3C, CC BY 3.0, https://www.w3.org/html/logo/. Alle Produktnamen gehören ihren Inhabern.
