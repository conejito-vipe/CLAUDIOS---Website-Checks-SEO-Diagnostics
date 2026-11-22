"""Crawler: Ebene 1 = Startseite, maximal 6 Ebenen, Seitenlimit je Stufe, nur eine Domain."""
from __future__ import annotations

import re
from collections import Counter, deque
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS
from .net import Gatekeeper, Response
from .snapshot import Page, Snapshot

ROBOTS_AGENT = "CLAUDIOS"
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico", ".pdf", ".zip", ".gz", ".rar",
            ".7z", ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".css", ".js", ".json", ".xml", ".txt", ".exe", ".dmg")
Progress = Callable[[str, int, int], None]


def norm(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), (p.netloc or "").lower(), p.path or "/", p.query, ""))


def build_page(resp: Response, depth: int) -> Page:
    ctype = (resp.header("content-type") or "").lower()
    page = Page(url=resp.url, depth=depth, status=resp.status, headers=resp.headers, cookies=resp.cookies,
                content_type=ctype, elapsed_ms=resp.elapsed_ms, size=len(resp.body), chain=resp.chain,
                blocked_redirect=resp.blocked_redirect, downgrade=resp.downgrade, truncated=resp.truncated)
    if "html" in ctype and resp.body:
        m = re.search(r"charset=([\w-]+)", ctype)
        try:
            text = resp.body.decode(m.group(1) if m else "utf-8", errors="replace")
        except LookupError:
            text = resp.body.decode("utf-8", errors="replace")
        page.html = text[: LIMITS.max_html_bytes]
    return page


def extract_links(page: Page, crawl_host: str) -> None:
    soup = page.soup
    if soup is None:
        return
    internal: dict[str, int] = {}
    external: dict[str, int] = {}
    insecure: dict[str, int] = {}
    base_tag = soup.find("base", href=True)  # relative Links gelten nach HTML-Standard gegen <base href>
    base_url = urljoin(page.url, str(base_tag["href"]).strip()) if base_tag is not None else page.url
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        p = urlsplit(absolute)
        if p.scheme not in ("http", "https") or not p.hostname:
            continue
        if p.scheme == "http":
            insecure[absolute] = 1
        elif p.hostname.lower() == crawl_host:
            internal[absolute] = 1
        else:
            external[absolute] = 1
    page.internal_links = list(internal)
    page.external_links = list(external)[: LIMITS.max_external_links_stored]
    page.insecure_links = list(insecure)[: LIMITS.max_external_links_stored]


def _parse_robots(lines: list[str]) -> RobotFileParser:
    rp = RobotFileParser()
    rp.parse(lines)
    rp.modified()  # sonst liefert can_fetch() immer False
    return rp


async def crawl(gk: Gatekeeper, snap: Snapshot, *, progress: Progress | None = None,
                respect_robots: bool = True) -> None:
    cap = LIMITS.pages_for(snap.level, snap.profile)
    report = progress or (lambda *_: None)
    first = await gk.fetch(snap.target.url)  # Fehler bei der Startseite sind immer fatal
    if first.blocked_redirect:
        if first.downgrade:
            raise ClaudiosError(E.NET_DOWNGRADE, url=first.blocked_redirect)
        raise ClaudiosError(E.NET_CROSS_SITE, host=urlsplit(first.blocked_redirect).hostname or "")
    page = build_page(first, 1)
    crawl_host = (urlsplit(first.url).hostname or "").lower()
    extract_links(page, crawl_host)
    snap.pages.append(page)
    report("crawl", 1, cap)

    robots = _parse_robots([])
    if respect_robots:
        try:
            fp = urlsplit(first.url)
            rr = await gk.fetch(urlunsplit((fp.scheme, fp.netloc, "/robots.txt", "", "")), max_bytes=500_000)
            if rr.status == 200:
                snap.robots_txt = rr.body.decode("utf-8", errors="replace")
                robots = _parse_robots(snap.robots_txt.splitlines())
        except ClaudiosError as e:
            if e.fatal:
                raise

    seen = {norm(first.url)}
    variants: Counter[str] = Counter()
    queue: deque[tuple[str, int]] = deque()

    def enqueue(p: Page) -> None:
        if p.depth >= LIMITS.max_depth:
            return
        for link in p.internal_links:
            n = norm(link)
            sp = urlsplit(n)
            if n in seen or sp.path.lower().endswith(SKIP_EXT) or len(seen) >= LIMITS.max_queued_urls:
                continue
            if sp.query:
                variants[sp.path] += 1
                if variants[sp.path] > LIMITS.max_query_variants_per_path:
                    continue
            seen.add(n)
            queue.append((n, p.depth + 1))

    enqueue(page)
    while queue:
        if len(snap.pages) >= cap:
            snap.skipped.append({"reason": "page_limit", "count": len(queue)})
            break
        url, depth = queue.popleft()
        if respect_robots and not robots.can_fetch(ROBOTS_AGENT, url):
            snap.skipped.append({"reason": "robots", "url": url})
            continue
        try:
            resp = await gk.fetch(url)
        except ClaudiosError as e:
            if e.fatal:
                raise
            snap.pages.append(Page(url=url, depth=depth, error=e.code.value))
            continue
        pg = build_page(resp, depth)
        extract_links(pg, crawl_host)
        snap.pages.append(pg)
        enqueue(pg)
        report("crawl", len(snap.pages), cap)
