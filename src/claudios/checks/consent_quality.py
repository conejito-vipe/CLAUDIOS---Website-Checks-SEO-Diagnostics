"""Qualität der Cookie-Banner (nur Hinweise). Ausgewertet wird nur der Teil, der schon im HTML steht: Banner, die erst
per JavaScript entstehen, sehen diese Prüfung nicht (dafür gibt es PRV-BRW-001 im Browser-Lauf)."""
from __future__ import annotations

import re

from ..core.registry import check
from ._util import F, S

_BANNER = re.compile(r"(cookie|consent|gdpr|dsgvo|cmp|privacy-?(banner|notice|popup)|datenschutz-?(banner|hinweis))", re.I)
_REJECT = ("reject", "decline", "deny", "refuse", "ablehn", "nur notwendige", "only necessary", "necessary only",
           "only essential", "essential only", "nur erforderliche", "nicht zustimmen", "verweiger")
_ACCEPT_EXACT = {"ok", "okay", "got it", "verstanden"}
_ACCEPT_PARTS = ("accept", "agree", "allow all", "zustimm", "akzeptier", "einverstanden", "alle zulassen")
_NECESSARY = re.compile(r"(necessary|essential|notwendig|erforderlich|required)", re.I)
_PRIVACY_LINK = re.compile(r"(datenschutz|privacy|cookie-?(policy|richtlinie|hinweis)|cookies)", re.I)


def _is_reject(text: str) -> bool:
    return any(part in text for part in _REJECT)


def _is_accept(text: str) -> bool:
    return not _is_reject(text) and (text in _ACCEPT_EXACT or any(part in text for part in _ACCEPT_PARTS))


def _labels(container) -> list[str]:
    out = []
    for element in container.find_all(["button", "a", "input"], limit=40):
        if element.name == "input" and str(element.get("type", "")).lower() not in ("button", "submit"):
            continue
        text = element.get_text(" ", strip=True) or str(element.get("value") or element.get("aria-label") or "")
        text = text.strip().lower()
        if 0 < len(text) <= 60:
            out.append(text)
    return out


def _containers(soup) -> list:
    tags = ["div", "section", "aside", "dialog", "form"]
    found = soup.find_all(tags, attrs={"id": _BANNER}, limit=30) + soup.find_all(tags, attrs={"class": _BANNER}, limit=30)
    unique = {id(el): el for el in found}
    outer = []
    for element in unique.values():
        if not any(id(parent) in unique for parent in element.parents):
            outer.append(element)
    return outer


@check("PRV-CNS-001",
       title="Qualität des Cookie-Banners (Hinweise) ## Quality of the cookie banner (hints)",
       why="Eine Einwilligung gilt nur, wenn Ablehnen genauso einfach ist wie Zustimmen und nichts vorausgewählt ist. Banner "
           "mit großem Akzeptieren-Knopf und versteckter Ablehnung sind eine häufige Beanstandung. ## Consent only counts if "
           "declining is as easy as agreeing and nothing is preselected. Banners with a big accept button and a hidden "
           "decline option are a common complaint.",
       method="Sucht im HTML aller gecrawlten Seiten Banner-Container (id oder class mit cookie, consent, gdpr, cmp …) und "
              "liest die Beschriftung ihrer Schaltflächen. Meldet fehlende Ablehnen-Schaltfläche, vorausgewählte Kontrollkästchen "
              "und fehlenden Datenschutz-Link. Banner, die per JavaScript entstehen, sieht die Prüfung nicht. Technischer "
              "Hinweis, keine Rechtsberatung. ## Looks in the HTML of all crawled pages for banner containers (id or class with "
              "cookie, consent, gdpr, cmp …) and reads the labels of their buttons. Reports a missing decline button, "
              "preselected checkboxes and a missing privacy link. Banners created by JavaScript are not seen by this check. "
              "Technical hint, not legal advice.",
       logic="Akzeptieren ohne Ablehnen auf der ersten Ebene oder vorausgewählte Kästchen: Hinweis. Kein Datenschutz-Link im "
             "Banner: Info. ## Accept without decline on the first level or preselected boxes: note. No privacy link in the "
             "banner: info.",
       fix="Eine gleichwertige Schaltfläche Ablehnen neben Alle akzeptieren anbieten, nichts vorauswählen und auf die "
           "Datenschutzerklärung verlinken. ## Offer an equal Reject button next to Accept all, preselect nothing and link to "
           "the privacy policy.",
       refs=["https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-032022-deceptive-design-patterns-social-media_en",
             "https://eur-lex.europa.eu/eli/dir/2002/58/oj"],
       profiles="sd")
def consent_quality(snap):
    no_reject, preselected, no_privacy = [], [], []
    for pg in snap.docs():
        for box in _containers(pg.soup):
            labels = _labels(box)
            if not any(_is_accept(label) for label in labels):
                continue
            if not any(_is_reject(label) for label in labels):
                no_reject.append(pg.url)
            for check_box in box.find_all("input", attrs={"type": "checkbox"}, limit=30):
                if check_box.has_attr("checked") and not _NECESSARY.search(
                        f"{check_box.get('name', '')} {check_box.get('id', '')} {check_box.get('value', '')}"):
                    preselected.append(pg.url)
                    break
            if not any(_PRIVACY_LINK.search(f"{a['href']} {a.get_text(' ', strip=True)}")
                       for a in box.find_all("a", href=True, limit=30)):
                no_privacy.append(pg.url)
    out = []
    if no_reject:
        out.append(F("PRV-CNS-001", S.NOTE, no_reject[0],
                     f"Banner mit Akzeptieren, aber ohne Ablehnen-Schaltfläche in der ersten Ebene ({len(set(no_reject))} Seite(n))",
                     f"Banner with accept but without a decline button on the first level ({len(set(no_reject))} page(s))"))
    if preselected:
        out.append(F("PRV-CNS-001", S.NOTE, preselected[0], "Banner mit vorausgewählten Kontrollkästchen",
                     "Banner with preselected checkboxes"))
    if no_privacy:
        out.append(F("PRV-CNS-001", S.INFO, no_privacy[0], "Banner ohne Link zur Datenschutzerklärung",
                     "Banner without a link to the privacy policy"))
    return out
