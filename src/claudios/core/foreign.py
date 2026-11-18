"""Nachträgliche Prüfung der Hosts, die Chromium und ZAP selbst aufgelöst haben (Fremdserver, Tracker, CDN).
Beide Werkzeuge lassen sich nicht an eine geprüfte IP binden. Jeder beobachtete Host wird danach per DoH aufgelöst.
Zeigt er auf eine nicht öffentliche Adresse, werden seine Daten verworfen und er wird gemeldet.
Grenze: Das erkennt den Fall, verhindert den Zugriff aber nicht (er ist dann schon geschehen).
Ein Host ohne Antwort gilt als unbekannt, nicht als verdächtig. Mehr als foreign_hosts_max Hosts oder eine
Überschreitung von foreign_budget_seconds werden als nicht geprüft gezählt."""
from __future__ import annotations

import ipaddress
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlsplit

from .guard import DohResolver, ip_allowed
from .limits import LIMITS

Lookup = Callable[[str, str], list[str]]


def lookup(host: str, rtype: str) -> list[str]:
    """DoH-Abfrage ohne Ausnahmen: ein Fehler bedeutet nur 'keine Antwort'."""
    try:
        return DohResolver()._query(host, rtype)
    except Exception:  # noqa: BLE001
        return []


def host_of(url: object) -> str:
    try:
        return (urlsplit(str(url)).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


@dataclass(frozen=True)
class Screen:
    private: tuple[str, ...] = ()
    unchecked: int = 0


def _classify(host: str, look: Lookup) -> str:
    """'public', 'private' oder 'unknown'."""
    try:
        literal = str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        literal = ""
    if literal:
        return "public" if ip_allowed(literal) else "private"
    ips = list(look(host, "A")) + list(look(host, "AAAA"))
    if not ips:
        return "unknown"
    try:
        return "public" if all(ip_allowed(ip) for ip in ips) else "private"
    except ValueError:
        return "unknown"


def screen(hosts: Iterable[str], look: Lookup = lookup, skip: Iterable[str] = ()) -> Screen:
    ignore = {str(s).lower().rstrip(".") for s in skip}
    wanted = sorted({str(h).lower().rstrip(".") for h in hosts if h} - ignore)
    todo = wanted[: LIMITS.foreign_hosts_max]
    unchecked = len(wanted) - len(todo)
    if not todo:
        return Screen((), unchecked)
    private: list[str] = []
    done = 0
    pool = ThreadPoolExecutor(max_workers=LIMITS.foreign_workers)
    futures = {pool.submit(_classify, host, look): host for host in todo}
    try:
        for future in as_completed(futures, timeout=LIMITS.foreign_budget_seconds):
            done += 1
            try:
                kind = future.result()
            except Exception:  # noqa: BLE001
                continue
            if kind == "private":
                private.append(futures[future])
    except TimeoutError:
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return Screen(tuple(sorted(private)), unchecked + len(todo) - done)


def _drop(page: dict, bad: set[str]) -> None:
    third = page.get("third_party")
    if isinstance(third, dict):
        page["third_party"] = {h: n for h, n in third.items() if str(h).lower() not in bad}
    for key in ("failed", "bad_status"):
        items = page.get(key)
        if isinstance(items, list):
            page[key] = [i for i in items if not (isinstance(i, dict) and host_of(i.get("url")) in bad)]
    cookies = page.get("cookies")
    if isinstance(cookies, list):
        page["cookies"] = [c for c in cookies
                           if not (isinstance(c, dict) and str(c.get("domain", "")).lstrip(".").lower() in bad)]


def screen_browser(data: dict, look: Lookup = lookup) -> Screen:
    """Prüft die Fremd-Hosts eines Browser-Laufs und verwirft die Daten der auffälligen. Ändert nichts, wenn alle
    Hosts unauffällig sind."""
    pages = [p for p in data.get("pages") or [] if isinstance(p, dict)]
    hosts = {str(h) for p in pages if isinstance(p.get("third_party"), dict) for h in p["third_party"]}
    result = screen(hosts, look)
    if result.private:
        bad = set(result.private)
        for page in pages:
            _drop(page, bad)
        data["foreign_private"] = list(result.private)
    if result.unchecked:
        data["foreign_unchecked"] = result.unchecked
    return result
