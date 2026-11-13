from __future__ import annotations

from ..core.errors import ErrorCode
from ..core.registry import check
from ._util import F, S


@check("SYS-ABT-001",
       title="Scan-Abbruch ## Scan abort",
       why="Ein abgebrochener Scan darf nie wie ein bestandener aussehen; der Grund muss sichtbar sein. ## "
           "An aborted scan must never look like a passed one; the reason must be visible.",
       method="Prüft, ob der Scan vorzeitig endete, und übernimmt den Fehlertext aus dem Fehlerkatalog. ## "
              "Checks whether the scan ended early and reports the error text from the error catalog.",
       logic="Kritisch bei ungültigem Zertifikat, sonst Fehler. ## Critical for an invalid certificate, otherwise error.",
       fix="Siehe Handlungshinweis in der Meldung. ## See the action hint in the message.",
       refs=["https://www.rfc-editor.org/rfc/rfc9110.html"])
def abort_finding(snap):
    if not snap.abort:
        return []
    sev = S.CRITICAL if snap.abort["code"] == ErrorCode.TLS_CERT.value else S.ERROR
    de, en = snap.abort["de"], snap.abort["en"]
    return [F("SYS-ABT-001", sev, snap.target.url,
              f"Scan abgebrochen: {de['title']}. {de['cause']} {de['action']}",
              f"Scan aborted: {en['title']}. {en['cause']} {en['action']}")]
