"""Internationales SEO jenseits von hreflang (SEO-HRF-001): Sprachangaben im HTML und im Header, Gegenstück zwischen
hreflang und lang, Canonical, unverschlüsselte hreflang-Ziele."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from ..core.crawler import norm
from ..core.registry import check
from ._util import F, S
from .seo_more import _alternates

GOOGLE = "https://developers.google.com/search/docs/"
_BCP47 = re.compile(r"^[a-z]{2,3}(-[a-z]{4})?(-([a-z]{2}|\d{3}))?$", re.I)
_WRONG_CODES = {"us", "gb", "eu", "en-uk", "en-eu"}


def _primary(code: str) -> str:
    return code.strip().lower().split("-")[0].split("_")[0]


@check("SEO-INT-001",
       title="Internationales SEO (Sprachangaben) ## International SEO (language signals)",
       why="Widersprüchliche Sprachangaben (lang, hreflang, Header, Canonical) führen dazu, dass Google die falsche Version "
           "ausspielt oder die Angaben ignoriert. ## Contradicting language signals (lang, hreflang, header, canonical) make "
           "Google serve the wrong version or ignore the annotations.",
       method="Vergleicht je Seite html lang, den hreflang-Eintrag auf sich selbst, den Header Content-Language und das "
              "Canonical. Prüft außerdem das Format des lang-Werts, häufige falsche hreflang-Codes (zum Beispiel en-uk statt "
              "en-GB) und hreflang-Ziele über unverschlüsseltes HTTP. ## Per page compares html lang, the hreflang entry for the "
              "page itself, the Content-Language header and the canonical. Also checks the format of the lang value, common wrong "
              "hreflang codes (for example en-uk instead of en-GB) and hreflang targets over unencrypted HTTP.",
       logic="hreflang auf sich selbst widerspricht lang: Warnung. Ungültiger lang-Wert, Header-Widerspruch, Canonical "
             "weicht vom hreflang ab, falscher Code, HTTP-Ziel: Hinweis. ## hreflang for the page itself contradicts lang: "
             "warning. Invalid lang value, header contradiction, canonical differs from hreflang, wrong code, HTTP target: note.",
       fix="lang, hreflang, Content-Language und Canonical derselben Seite auf dieselbe Sprache und dieselbe Adresse "
           "abstimmen und Sprachcodes nach BCP 47 schreiben (en-GB). ## Align lang, hreflang, Content-Language and canonical of "
           "the same page to the same language and address and write language codes per BCP 47 (en-GB).",
       refs=[GOOGLE + "specialty/international/localized-versions", "https://www.rfc-editor.org/rfc/rfc5646"], profiles="sd")
def international(snap):
    bad_lang, mismatch, header, canon, wrong, insecure = [], [], [], [], [], []
    for pg in snap.docs():
        soup = pg.soup
        root = soup.find("html")
        lang = str(root.get("lang", "")).strip() if root else ""
        if lang and not _BCP47.match(lang):
            bad_lang.append(pg.url)
        alternates = _alternates(pg)
        own = norm(pg.url)
        for code, target in alternates:
            if code.lower() in _WRONG_CODES:
                wrong.append(pg.url)
            if target.startswith("http:"):
                insecure.append(pg.url)
        selfs = [code for code, target in alternates if target == own and code.lower() != "x-default"]
        if lang and selfs and _primary(selfs[0]) != _primary(lang):
            mismatch.append(pg.url)
        if selfs:
            link = next((x for x in soup.find_all("link", href=True) if "canonical" in (x.get("rel") or [])), None)
            if link is not None and norm(urljoin(pg.url, str(link["href"]))) != own:
                canon.append(pg.url)
        content_language = pg.headers.get("content-language", "").split(",")[0].strip()
        if lang and content_language and _primary(content_language) != _primary(lang):
            header.append(pg.url)
    out = []
    if mismatch:
        out.append(F("SEO-INT-001", S.WARNING, mismatch[0], f"hreflang der Seite selbst widerspricht html lang ({len(set(mismatch))} Seite(n))",
                     f"hreflang of the page itself contradicts html lang ({len(set(mismatch))} page(s))"))
    for urls, de, en in (
            (bad_lang, "Ungültiger lang-Wert", "Invalid lang value"),
            (header, "Header Content-Language widerspricht html lang", "Content-Language header contradicts html lang"),
            (canon, "Canonical weicht von der hreflang-Adresse der Seite ab", "Canonical differs from the hreflang address of the page"),
            (wrong, "Häufig falscher hreflang-Code (zum Beispiel en-uk, us, gb)", "Commonly wrong hreflang code (for example en-uk, us, gb)"),
            (insecure, "hreflang-Ziel über unverschlüsseltes HTTP", "hreflang target over unencrypted HTTP")):
        if urls:
            out.append(F("SEO-INT-001", S.NOTE, urls[0], f"{de} ({len(set(urls))} Seite(n))",
                         f"{en} ({len(set(urls))} page(s))"))
    return out
