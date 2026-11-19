"""Passive Analyse mit OWASP ZAP (nur Stufe 2). Die Daten liefert die Probe core/probe_zap.py."""
from __future__ import annotations

from ..core.registry import check
from ._util import CheckSkipped, F, S

RISK = {"high": S.ERROR, "medium": S.WARNING, "low": S.NOTE, "informational": S.INFO}


@check("ZAP-PAS-001",
       title="Passive Analyse mit OWASP ZAP ## Passive analysis with OWASP ZAP",
       why="ZAP wertet den echten Datenverkehr eines Browsers aus (Header, Cookies, Skripte, Formulare) mit "
           "Hunderten bewährter Regeln und findet Schwachstellen, die weder das HTML noch einzelne Header-Prüfungen "
           "zeigen. Das ergänzt die übrigen Prüfungen um eine unabhängige zweite Meinung. ## ZAP evaluates the real "
           "traffic of a browser (headers, cookies, scripts, forms) with hundreds of proven rules and finds "
           "weaknesses that neither the HTML nor single header checks show. This adds an independent second "
           "opinion to the other checks.",
       method="Nur nach Verifizierung (Stufe 2). Startet ZAP als Daemon nur auf 127.0.0.1 (zufälliger Port und "
              "API-Schlüssel, ohne Update-Prüfung) und lädt bis zu 10 Seiten der Stichprobe in Chromium durch ZAP. "
              "Es werden nur die passiven Regeln ausgewertet, ein aktiver Scan oder Spider wird nie gestartet. "
              "Browser und ZAP verbinden direkt und nicht über den Gatekeeper, ZAP löst Namen selbst auf. Das "
              "Root-Zertifikat von ZAP wird nicht installiert, Chromium bekommt nur dessen SPKI-Hash für diesen "
              "Lauf; andere Zertifikatsfehler werden nie ignoriert. Der Verkehr liegt in einem Zwischenordner, der "
              "danach gelöscht wird, im Bericht stehen nur Regelname, Risiko, Adresse und CWE. Fehlt ein Werkzeug, "
              "hat ZAP keine passiven Regeln oder schlägt der Lauf fehl, gilt die Prüfung als nicht ausgeführt. ## "
              "Only after verification (level 2). Starts ZAP as a daemon only on 127.0.0.1 (random port and API "
              "key, no update check) and loads up to 10 pages of the sample in Chromium through ZAP. Only the "
              "passive rules are evaluated, an active scan or spider is never started. Browser and ZAP connect "
              "directly and not through the gatekeeper, ZAP resolves names itself. The root certificate of ZAP is "
              "not installed, Chromium only gets its SPKI hash for this run; other certificate errors are never "
              "ignored. The traffic lies in a temporary folder that is deleted afterwards, the report shows only "
              "rule name, risk, address and CWE. If a tool is missing, ZAP has no passive rules or the run "
              "fails, the check counts as not executed.",
       logic="Risiko laut ZAP: hoch: Fehler, mittel: Warnung, niedrig: Hinweis, informativ: Info. Je Regel ein "
             "Befund mit Anzahl. Auswertung nicht abgeschlossen: Info. ## Risk according to ZAP: high: error, "
             "medium: warning, low: note, informational: info. One finding per rule with count. Evaluation not "
             "finished: info.",
       fix="Die Regel im ZAP-Alert-Verzeichnis nachschlagen (Regelname und CWE im Beleg) und die dort beschriebene "
           "Korrektur umsetzen. ## Look the rule up in the ZAP alert directory (rule name and CWE in the evidence) "
           "and apply the fix described there.",
       refs=["https://www.zaproxy.org/docs/alerts/", "https://www.zaproxy.org/"],
       profiles="sd", kind="active", source="tool", needs=("java", "zap", "node", "playwright"))
def zap_passive(snap):
    data = snap.extra.get("zap")
    if data is None:
        raise CheckSkipped("no_zap_data")
    if data.get("skip"):
        raise CheckSkipped(str(data["skip"]))
    groups: dict[tuple[str, str], dict] = {}
    for alert in data["alerts"]:
        group = groups.setdefault((alert["name"], alert["risk"].lower()), {
            "count": 0, "url": alert["url"], "cwe": alert["cwe"], "plugin": alert["plugin"]})
        group["count"] += 1
    out = []
    for (name, risk), group in sorted(groups.items()):
        cwe = f"CWE-{group['cwe']} " if group["cwe"] not in ("", "0", "-1") else ""
        out.append(F("ZAP-PAS-001", RISK.get(risk, S.NOTE), group["url"], f"ZAP: {name} ({group['count']}x)",
                     f"ZAP: {name} ({group['count']}x)", f"{cwe}Regel {group['plugin']}".strip()))
    if not data.get("complete"):
        out.append(F("ZAP-PAS-001", S.INFO, snap.target.url,
                     "Die passive Auswertung von ZAP war beim Abruf der Funde noch nicht abgeschlossen",
                     "The passive evaluation of ZAP was not finished when the findings were fetched"))
    return out
