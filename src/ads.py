"""ads.txt und app-ads.txt. Die Dateien stammen aus der Probe-Phase und werden nur bei erkannter Werbung geholt."""
from __future__ import annotations

from ..core.registry import check
from ._util import CheckSkipped, F, S

IAB = "https://iabtechlab.com/ads-txt/"
IAB_APP = "https://iabtechlab.com/app-ads-txt/"
_VARIABLES = {"contact", "subdomain", "inventorypartnerdomain", "ownerdomain", "managerdomain"}


def _parse(text: str) -> tuple[int, list[str]]:
    valid, bad = 0, []
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, sep, _rest = line.partition("=")
        if sep and "," not in key and key.strip().lower() in _VARIABLES:
            continue
        fields = [x.strip() for x in line.split(",")]
        if len(fields) >= 3 and "." in fields[0] and fields[1] and fields[2].upper() in ("DIRECT", "RESELLER"):
            valid += 1
        else:
            bad.append(line)
    return valid, bad


@check("ADS-TXT-001",
       title="ads.txt und app-ads.txt ## ads.txt and app-ads.txt",
       why="Die Datei ads.txt nennt die Anbieter, die Ihre Werbeflächen verkaufen dürfen. Fehlt sie oder ist sie "
           "fehlerhaft, können gefälschte Anbieter Werbung vermitteln, und Werbepartner zahlen weniger oder gar "
           "nichts. ## The ads.txt file lists the vendors allowed to sell your ad inventory. If it is missing "
           "or faulty, fake vendors can sell ads and ad partners pay less or nothing.",
       method="Wird nur ausgeführt, wenn auf den Seiten Werbung erkannt wurde (Skripte bekannter Werbenetzwerke "
              "oder adsbygoogle). Dann werden /ads.txt und /app-ads.txt je einmal über den Gatekeeper abgerufen "
              "und Zeile für Zeile geprüft: Domain, Konto-ID, DIRECT oder RESELLER; Variablen wie contact= "
              "sind erlaubt. app-ads.txt wird nur auf Syntax geprüft, ihr Fehlen ist kein Befund. ## Runs only "
              "if advertising was detected on the pages (scripts of known ad networks or adsbygoogle). Then "
              "/ads.txt and /app-ads.txt are fetched once each through the gatekeeper and checked line by line: "
              "domain, account ID, DIRECT or RESELLER; variables such as contact= are allowed. app-ads.txt is "
              "only checked for syntax, its absence is not a finding.",
       logic="Werbung erkannt, aber keine ads.txt (404): Warnung. HTML statt Text oder keine gültigen Einträge: "
             "Warnung. Ungültige Zeilen oder anderer HTTP-Status: Hinweis. ## Advertising detected but no "
             "ads.txt (404): warning. HTML instead of text or no valid entries: warning. Invalid lines or other "
             "HTTP status: note.",
       fix="Im Wurzelverzeichnis eine Datei ads.txt mit Zeilen wie 'google.com, pub-0000000000000000, DIRECT, "
           "f08c47fec0942fa0' anlegen (Werte vom Werbeanbieter). ## Create an ads.txt file in the web root with "
           "lines such as 'google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0' (values from the ad "
           "provider).",
       refs=[IAB, IAB_APP], profiles="sd", source="network")
def ads_txt(snap):
    data = snap.extra.get("ads")
    if data is None:
        raise CheckSkipped("no_ads_data")
    if not data["detected"]:
        return []
    files = {f["path"]: f for f in data["files"]}
    main = files.get("/ads.txt")
    if main is None or main["error"]:
        raise CheckSkipped("ads_txt_unreachable")
    url, out = snap.target.url, []
    seen = ", ".join(data["detected"])[:120]
    if main["status"] in (404, 410):
        out.append(F("ADS-TXT-001", S.WARNING, url, "Werbung erkannt, aber keine ads.txt vorhanden",
                     "Advertising detected but no ads.txt present", seen))
    elif main["status"] != 200:
        out.append(F("ADS-TXT-001", S.NOTE, url, f"ads.txt antwortet mit HTTP {main['status']}",
                     f"ads.txt answers with HTTP {main['status']}"))
    for path in ("/ads.txt", "/app-ads.txt"):
        rec = files.get(path)
        if rec is None or rec["status"] != 200:
            continue
        if "html" in rec["content_type"]:
            out.append(F("ADS-TXT-001", S.WARNING, url, f"{path} liefert HTML statt Text (vermutlich eine Fehlerseite)",
                         f"{path} returns HTML instead of text (probably an error page)"))
            continue
        valid, bad = _parse(rec["text"])
        if valid == 0:
            out.append(F("ADS-TXT-001", S.WARNING, url, f"{path} enthält keine gültigen Einträge",
                         f"{path} contains no valid entries"))
        if bad:
            out.append(F("ADS-TXT-001", S.NOTE, url, f"{path}: {len(bad)} ungültige Zeile(n)",
                         f"{path}: {len(bad)} invalid line(s)", bad[0][:80]))
    return out