"""TLS-Prüfungen mit sslyze (nur als externer Prozess in eigener Python-Umgebung).
Fehlt das Werkzeug oder ist die Ausgabe unlesbar, gilt die Prüfung als nicht ausgeführt, nie als bestanden."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .. import paths
from ..components.manager import tool_path
from ..core.errors import ClaudiosError
from ..core.guard import DohResolver, ip_allowed
from ..core.limits import LIMITS
from ..core.registry import check
from ..core.toolrunner import run_tool
from ._util import CheckSkipped, F, S

# Schreibweise der festen IP für sslyze: Hostname, Port, IP in geschweiften Klammern.
# Geprüft im Workflow "pip-Sperrliste": host:443{ip} funktioniert, host{ip}:443 liefert einen Verbindungsfehler.
TARGET_FORMAT = "{host}:443{{{ip}}}"
PASSIVE_OPTIONS = ["--sslv2", "--sslv3", "--tlsv1", "--tlsv1_1", "--tlsv1_2", "--tlsv1_3", "--certinfo"]
ACTIVE_OPTIONS = ["--heartbleed", "--robot", "--openssl_ccs"]
PROTOCOLS = (("ssl_2_0_cipher_suites", "SSL 2.0", S.ERROR), ("ssl_3_0_cipher_suites", "SSL 3.0", S.ERROR),
             ("tls_1_0_cipher_suites", "TLS 1.0", S.WARNING), ("tls_1_1_cipher_suites", "TLS 1.1", S.WARNING))
WEAK = ("RC4", "3DES", "DES-CBC", "DES_CBC", "NULL", "EXPORT", "MD5", "ANON", "ADH-", "AECDH")
RFC8996 = "https://www.rfc-editor.org/rfc/rfc8996"
SSLYZE = "https://github.com/nabla-c0d3/sslyze"


def _target(snap) -> str:
    """Hostname plus eine per DoH aufgelöste, als öffentlich geprüfte IP (kein erneutes Auflösen durch sslyze)."""
    if snap.target.loopback:
        raise CheckSkipped("localhost")
    host, resolver, ips = snap.target.host, DohResolver(), []
    for rtype in ("A", "AAAA"):
        try:
            ips += resolver._query(host, rtype)
        except Exception:  # noqa: BLE001 – ein DNS-Fehler bedeutet nur: nicht prüfbar
            pass
    if not ips or not all(ip_allowed(ip) for ip in ips):
        raise CheckSkipped("target_not_public")
    ip = next((i for i in ips if ":" not in i), ips[0])
    return TARGET_FORMAT.format(host=host, ip=ip)


def _scan(snap, options: list[str]) -> dict:
    python = tool_path("sslyze")
    if python is None:
        raise CheckSkipped("tool_not_found")
    target = _target(snap)
    with tempfile.TemporaryDirectory(dir=paths.cache_dir()) as tmp:
        out = Path(tmp) / "result.json"
        try:
            run_tool([python, "-m", "sslyze", *options, "--json_out", out, target], cwd=tmp,
                     timeout=LIMITS.sslyze_timeout_seconds, extra_env={"PYTHONNOUSERSITE": "1"})
        except ClaudiosError:
            raise CheckSkipped("tool_failed") from None
        try:
            data = json.loads(out.read_text("utf-8"))
        except (OSError, ValueError):
            raise CheckSkipped("tool_output_unreadable") from None
    results = data.get("server_scan_results") if isinstance(data, dict) else None
    first = results[0] if isinstance(results, list) and results else None
    if not isinstance(first, dict):
        raise CheckSkipped("tool_output_unreadable")
    scan = first.get("scan_result")
    if first.get("scan_status") != "COMPLETED" or not isinstance(scan, dict):
        raise CheckSkipped("tool_failed")
    return scan


def _result(scan: dict, key: str) -> dict | None:
    entry = scan.get(key)
    if not isinstance(entry, dict) or entry.get("status") != "COMPLETED":
        return None
    result = entry.get("result")
    return result if isinstance(result, dict) else None


def _accepted(scan: dict, key: str) -> list[str] | None:
    result = _result(scan, key)
    items = result.get("accepted_cipher_suites") if result else None
    if not isinstance(items, list):
        return None
    names = []
    for item in items:
        suite = item.get("cipher_suite") if isinstance(item, dict) else None
        names.append(str(suite.get("name", "")) if isinstance(suite, dict) else "")
    return names


def _weak(name: str) -> bool:
    upper = name.upper()
    return any(part in upper for part in WEAK)


def _certificate(scan: dict, url: str) -> list:
    result = _result(scan, "certificate_info")
    out = []
    for dep in (result.get("certificate_deployments") if result else None) or []:
        if not isinstance(dep, dict):
            continue
        if dep.get("leaf_certificate_subject_matches_hostname") is False:
            out.append(F("TLS-PRO-001", S.ERROR, url, "Das Zertifikat passt nicht zum Hostnamen",
                         "The certificate does not match the host name"))
        checks = [v for v in dep.get("path_validation_results") or [] if isinstance(v, dict)]
        if checks and not any(v.get("was_validation_successful") for v in checks):
            out.append(F("TLS-PRO-001", S.ERROR, url, "Die Zertifikatskette wird von keinem Vertrauensspeicher akzeptiert",
                         "The certificate chain is not accepted by any trust store"))
    return out


@check("TLS-PRO-001",
       title="TLS-Protokolle und Cipher (sslyze) ## TLS protocols and ciphers (sslyze)",
       why="Alte Protokolle (SSL 2.0/3.0, TLS 1.0/1.1) und schwache Cipher (RC4, 3DES, Export) sind knackbar. Wer "
           "sie erlaubt, gefährdet die Vertraulichkeit der Verbindung, auch wenn moderne Browser sie meiden. "
           "Fehlt TLS 1.3, geht Geschwindigkeit und Sicherheit verloren. ## Old protocols (SSL 2.0/3.0, TLS "
           "1.0/1.1) and weak ciphers (RC4, 3DES, export) can be broken. Allowing them endangers the "
           "confidentiality of the connection even if modern browsers avoid them. Without TLS 1.3 speed and "
           "security are lost.",
       method="Startet sslyze (eigene Python-Umgebung, externer Prozess, nur Handshakes ohne Anwendungsdaten) "
              "gegen die zuvor per DoH aufgelöste, als öffentlich geprüfte IP. sslyze verbindet direkt und nicht "
              "über den Gatekeeper, es macht einige Dutzend Handshakes und kennt unsere Drosselung nicht. "
              "Ausgewertet werden akzeptierte Protokolle und Cipher sowie die Zertifikatsprüfung. Bei "
              "fehlendem Werkzeug, Fehlschlag oder unlesbarer Ausgabe gilt die Prüfung als nicht ausgeführt. ## "
              "Starts sslyze (own Python environment, external process, handshakes only, no application data) "
              "against the IP previously resolved via DoH and verified as public. sslyze connects directly and "
              "not through the gatekeeper, it performs a few dozen handshakes and does not know our throttling. "
              "Accepted protocols and ciphers and the certificate validation are evaluated. With a missing "
              "tool, a failure or unreadable output the check counts as not executed.",
       logic="SSL 2.0/3.0 akzeptiert, kein TLS 1.2/1.3, ungültige Kette oder falscher Hostname: Fehler. TLS 1.0/1.1 "
             "oder schwache Cipher: Warnung. Kein TLS 1.3: Info. ## SSL 2.0/3.0 accepted, no TLS 1.2/1.3, invalid "
             "chain or wrong host name: error. TLS 1.0/1.1 or weak ciphers: warning. No TLS 1.3: info.",
       fix="Nur TLS 1.2 und 1.3 aktivieren und eine moderne Cipher-Liste verwenden (zum Beispiel die Vorlage des "
           "Mozilla SSL Configuration Generators). ## Enable only TLS 1.2 and 1.3 and use a modern cipher list "
           "(for example the template of the Mozilla SSL Configuration Generator).",
       refs=[RFC8996, SSLYZE, "https://ssl-config.mozilla.org/"],
       profiles="sd", source="tool", needs=("sslyze",))
def protocols(snap):
    scan = _scan(snap, PASSIVE_OPTIONS)
    url, out, known = snap.target.url, [], 0
    for key, label, severity in PROTOCOLS:
        names = _accepted(scan, key)
        if names is None:
            continue
        known += 1
        if names:
            out.append(F("TLS-PRO-001", severity, url, f"Der Server akzeptiert das veraltete Protokoll {label}",
                         f"The server accepts the outdated protocol {label}"))
    t12, t13 = _accepted(scan, "tls_1_2_cipher_suites"), _accepted(scan, "tls_1_3_cipher_suites")
    if known == 0 and t12 is None and t13 is None:
        raise CheckSkipped("tool_output_unreadable")
    if t12 == [] and t13 == []:
        out.append(F("TLS-PRO-001", S.ERROR, url, "Der Server bietet weder TLS 1.2 noch TLS 1.3 an",
                     "The server offers neither TLS 1.2 nor TLS 1.3"))
    elif t13 == []:
        out.append(F("TLS-PRO-001", S.INFO, url, "TLS 1.3 wird nicht angeboten", "TLS 1.3 is not offered"))
    weak = [name for name in (t12 or []) if _weak(name)]
    if weak:
        out.append(F("TLS-PRO-001", S.WARNING, url, f"{len(weak)} schwache Cipher in TLS 1.2 erlaubt",
                     f"{len(weak)} weak ciphers allowed in TLS 1.2", ", ".join(weak[:3])))
    out.extend(_certificate(scan, url))
    return out


@check("TLS-ATK-001",
       title="TLS-Schwachstellen (Heartbleed, ROBOT, CCS-Injection) ## TLS vulnerabilities (Heartbleed, ROBOT, CCS injection)",
       why="Heartbleed und CCS-Injection erlauben Angreifern, Schlüssel oder Daten aus dem Speicher des Servers zu "
           "lesen beziehungsweise Verbindungen mitzuschneiden, ROBOT entschlüsselt RSA-Verkehr. Diese Lücken sind "
           "alt, kommen aber auf ungepflegten Servern noch vor. ## Heartbleed and CCS injection let attackers read "
           "keys or data from the server memory or intercept connections, ROBOT decrypts RSA traffic. These "
           "flaws are old but still occur on unmaintained servers.",
       method="Startet sslyze mit den Tests Heartbleed, ROBOT und OpenSSL-CCS. Diese senden gezielt veränderte "
              "Handshake-Nachrichten und sind deshalb aktiv: Die Prüfung läuft nur nach Verifizierung (Stufe 2). "
              "sslyze verbindet direkt zur zuvor als öffentlich geprüften IP. ## Starts sslyze with the "
              "Heartbleed, ROBOT and OpenSSL CCS tests. They send deliberately altered handshake messages and are "
              "therefore active: the check only runs after verification (level 2). sslyze connects directly to "
              "the IP previously verified as public.",
       logic="Heartbleed oder CCS-Injection verwundbar: kritisch. ROBOT verwundbar: Fehler. ## Vulnerable to "
             "Heartbleed or CCS injection: critical. Vulnerable to ROBOT: error.",
       fix="OpenSSL beziehungsweise die TLS-Bibliothek des Servers sofort aktualisieren und RSA-Schlüsselaustausch "
           "abschalten. ## Update OpenSSL or the TLS library of the server immediately and disable RSA key exchange.",
       refs=["https://heartbleed.com/", "https://robotattack.org/", SSLYZE],
       profiles="sd", kind="active", source="tool", needs=("sslyze",))
def attacks(snap):
    scan = _scan(snap, ACTIVE_OPTIONS)
    url, out, known = snap.target.url, [], 0
    heart = _result(scan, "heartbleed")
    ccs = _result(scan, "openssl_ccs_injection")
    robot = _result(scan, "robot")
    known = sum(item is not None for item in (heart, ccs, robot))
    if known == 0:
        raise CheckSkipped("tool_output_unreadable")
    if heart and heart.get("is_vulnerable_to_heartbleed") is True:
        out.append(F("TLS-ATK-001", S.CRITICAL, url, "Der Server ist für Heartbleed verwundbar",
                     "The server is vulnerable to Heartbleed"))
    if ccs and ccs.get("is_vulnerable_to_ccs_injection") is True:
        out.append(F("TLS-ATK-001", S.CRITICAL, url, "Der Server ist für CCS-Injection verwundbar",
                     "The server is vulnerable to CCS injection"))
    if robot and str(robot.get("robot_result", "")).startswith("VULNERABLE"):
        out.append(F("TLS-ATK-001", S.ERROR, url, "Der Server ist für ROBOT verwundbar",
                     "The server is vulnerable to ROBOT", str(robot.get("robot_result"))[:40]))
    return out
