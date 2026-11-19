"""Aktive Prüfung auf öffentlich erreichbare sensible Dateien (nur Stufe 2).
Die Daten liefert die Probe core/probe_paths.py."""
from __future__ import annotations

from urllib.parse import urljoin

from ..core.registry import check
from ._util import CheckSkipped, F, S

WSTG = ("https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/"
        "02-Configuration_and_Deployment_Management_Testing/"
        "04-Review_Old_Backup_and_Unreferenced_Files_for_Sensitive_Information")

# Art -> (Schweregrad, deutscher Text, englischer Text)
KINDS = {
    "vcs": (S.CRITICAL, "Die Versionsverwaltung ist öffentlich abrufbar: {path} (Quellcode und Zugangsdaten können offenliegen)",
            "The version control data is publicly reachable: {path} (source code and credentials may be exposed)"),
    "env": (S.CRITICAL, "Eine Konfigurationsdatei mit Zugangsdaten ist öffentlich abrufbar: {path}",
            "A configuration file with credentials is publicly reachable: {path}"),
    "htpasswd": (S.CRITICAL, "Eine Passwortdatei ist öffentlich abrufbar: {path}",
                 "A password file is publicly reachable: {path}"),
    "backup": (S.ERROR, "Ein Backup oder Datenbank-Dump ist öffentlich abrufbar: {path}",
               "A backup or database dump is publicly reachable: {path}"),
    "phpinfo": (S.ERROR, "phpinfo() ist öffentlich erreichbar: {path} (verrät Konfiguration und Pfade)",
                "phpinfo() is publicly reachable: {path} (reveals configuration and paths)"),
    "status": (S.ERROR, "Die Serverstatus-Seite ist öffentlich erreichbar: {path}",
               "The server status page is publicly reachable: {path}"),
    "webconfig": (S.ERROR, "Die Datei web.config ist öffentlich abrufbar: {path}",
                  "The web.config file is publicly reachable: {path}"),
    "dsstore": (S.WARNING, "Die Datei {path} ist öffentlich abrufbar und verrät Dateinamen",
                "The file {path} is publicly reachable and reveals file names"),
    "listing": (S.WARNING, "Verzeichnisauflistung ist aktiv: {path}", "Directory listing is enabled: {path}"),
    "admin": (S.NOTE, "Eine Verwaltungsoberfläche ist öffentlich erreichbar: {path}",
              "An administration interface is publicly reachable: {path}"),
}


@check("EXP-PTH-001",
       title="Öffentlich erreichbare sensible Dateien (aktive Prüfung) ## Publicly reachable sensitive files (active check)",
       why="Vergessene Dateien wie .env, .git, Backups oder Datenbank-Dumps enthalten oft Passwörter und Quellcode "
           "und werden von Angreifern automatisiert gesucht. Verzeichnisauflistungen und offene Verwaltungsseiten "
           "erleichtern weitere Angriffe. ## Forgotten files such as .env, .git, backups or database dumps often "
           "contain passwords and source code and are searched for automatically by attackers. Directory listings "
           "and open administration pages make further attacks easier.",
       method="Aktive Prüfung, nur nach Verifizierung (Stufe 2): Ruft 27 feste Pfade per GET über den gedrosselten "
              "Gatekeeper ab (nur HTTPS, keine Weiterleitungen, keine Payloads, kein Raten, keine Anmeldeversuche). "
              "Ein Treffer zählt nur, wenn Statuscode 200 und der Inhalt zur Datei passt (zum Beispiel 'ref: refs/' "
              "bei .git/HEAD), damit Seiten, die auf alles mit 200 antworten, keinen Fehlalarm auslösen. Die "
              "Inhalte werden nie gespeichert, im Bericht stehen nur der Pfad und die Art. Der Zielserver kann die "
              "Abrufe protokollieren, und Schutzsysteme können sie als Scan werten. ## Active check, only after "
              "verification (level 2): requests 27 fixed paths via GET through the throttled gatekeeper (HTTPS only, "
              "no redirects, no payloads, no guessing, no login attempts). A hit only counts with status code 200 "
              "and content that matches the file (for example 'ref: refs/' for .git/HEAD), so that sites answering "
              "everything with 200 do not trigger false alarms. The content is never stored, the report shows only "
              "the path and the kind. The target server may log the requests, and protection systems may treat "
              "them as a scan.",
       logic="Versionsverwaltung, .env, .htpasswd: kritisch. Backup/Dump, phpinfo, server-status, web.config: Fehler. "
             ".DS_Store, Verzeichnisauflistung: Warnung. Verwaltungsseite öffentlich: Hinweis. Antwortet kein Pfad: "
             "nicht ausgeführt. ## Version control, .env, .htpasswd: critical. Backup/dump, phpinfo, server-status, "
             "web.config: error. .DS_Store, directory listing: warning. Administration page public: note. No path "
             "answers: not executed.",
       fix="Die Datei vom Webserver entfernen oder den Zugriff sperren, enthaltene Passwörter sofort ändern und "
           "Verzeichnisauflistung abschalten. ## Remove the file from the web server or block access, change any "
           "contained passwords immediately and disable directory listing.",
       refs=[WSTG, "https://cwe.mitre.org/data/definitions/538.html"],
       profiles="sd", kind="active", source="network")
def exposed_paths(snap):
    data = snap.extra.get("paths")
    if data is None:
        raise CheckSkipped("no_path_data")
    if data["total"] and data["errors"] >= data["total"]:
        raise CheckSkipped("paths_unreachable")
    base = snap.pages[0].url if snap.pages else snap.target.url
    out = []
    for rec in data["checked"]:
        if not rec["hit"]:
            continue
        severity, de, en = KINDS[rec["kind"]]
        out.append(F("EXP-PTH-001", severity, urljoin(base, "/" + rec["path"]),
                     de.format(path=rec["path"]), en.format(path=rec["path"]), rec["path"]))
    return out
