import time
import zipfile
from pathlib import Path

import pytest

from claudios.checks import hardening, tools_html
from claudios.components import manager
from claudios.core import seoprobe
from claudios.core.crawler import extract_links
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.guard import normalize_input
from claudios.core.redact import SECRET_PATTERNS, redact_text, redact_url
from claudios.core.snapshot import Page, Snapshot, parse_set_cookie
from claudios.core.toolrunner import ToolResult

BIG = 100_000
LIMIT = 3.0  # Sekunden; lineare Muster brauchen Millisekunden
CASES = {
    "long-token": "a" * BIG + "@",
    "dotted-token": "a." * (BIG // 2),
    "jwt-like": "eyJ0123456789-" * (BIG // 14),
    "key-header": "-----BEGIN " + "A " * (BIG // 2),
    "spaces-after-keyword": "password" + " " * BIG + "x",
    "spaces-after-bearer": "bearer" + " " * BIG + "x",
    "newlines": "\n" * BIG,
    "unclosed-loc": "<loc>a" + " " * BIG,
    "dashes": "-" * BIG,
}


def took(job) -> float:
    start = time.perf_counter()
    job()
    return time.perf_counter() - start


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    return tmp_path


@pytest.mark.parametrize("name", list(CASES))
def test_own_patterns_stay_fast_on_hostile_text(name):
    text = CASES[name]
    jobs = {
        "redact_text": lambda: redact_text(text),
        "sitemap <loc>": lambda: seoprobe._LOC.findall(text),
        "robots Sitemap:": lambda: seoprobe._SITEMAP_LINE.findall(text),
        "e-mail check": lambda: list(hardening._EMAIL.finditer(text)),
    }
    jobs.update({f"secret:{key}": (lambda pat=pat: pat.findall(text)) for key, pat in SECRET_PATTERNS.items()})
    for label, job in jobs.items():
        assert took(job) < LIMIT, f"{label} ist bei '{name}' zu langsam"


def test_redaction_still_finds_a_jwt_and_an_address():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk"
    out = redact_text(f"token {jwt} and mail a.b@example.com x")
    assert jwt not in out and "[REDACTED:jwt]" in out and "[email]" in out


def test_sitemap_and_robots_patterns_keep_their_results():
    assert seoprobe._locs("<loc> https://example.com/a?x=1&amp;y=2 </loc><loc></loc><LOC>https://b.test/</LOC>") == [
        "https://example.com/a?x=1&y=2", "https://b.test/"]
    robots = "User-agent: *\n  Sitemap: https://example.com/s.xml\nsitemap:https://example.com/t.xml\n"
    assert seoprobe._SITEMAP_LINE.findall(robots) == ["https://example.com/s.xml", "https://example.com/t.xml"]


def test_long_urls_and_cookie_lines_are_handled_quickly():
    assert took(lambda: redact_url("https://example.com/?" + "a=1&" * 20000)) < LIMIT
    assert took(lambda: parse_set_cookie("a=" + "x" * BIG + "; " + "k=v; " * 5000)) < LIMIT


def make_snap(html: str) -> Snapshot:
    snap = Snapshot(target=normalize_input("example.com"), level=1, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html=html, content_type="text/html"))
    snap.status = "complete"
    return snap


def hostile_html() -> str:
    return ("<!doctype html><html lang=en><head><title>" + "t" * 5000 + "</title></head><body>"
            + "<div>" * 1500 + "a@b.cc eyJ0123456789- " * 3000 + "</div>" * 1500
            + "".join(f'<a href="/p{i}#x{i}" target=_blank>x</a>' for i in range(3000))
            + "<img src=a><input type=password>" + "<p style=x onclick=y>" * 1500 + "</body></html>")


def test_a_hostile_page_neither_hangs_nor_crashes_a_check():
    snap = make_snap(hostile_html())
    start = time.perf_counter()
    _, executed = run_checks(snap, 1, "standard")
    assert time.perf_counter() - start < 30
    assert [cid for cid, status in executed.items() if status.startswith("failed")] == []


def test_many_links_are_capped():
    html = "".join(f'<a href="https://x{i}.example/">l</a>' for i in range(20000))
    page = Page(url="https://example.com/", depth=1, status=200, html=html, content_type="text/html")
    assert took(lambda: extract_links(page, "example.com")) < 5.0
    assert len(page.external_links) <= 500


def run_vnu(monkeypatch, env, output: str) -> str:
    monkeypatch.setattr(tools_html, "tool_path", lambda name: Path("/t") / name / "tool")
    monkeypatch.setattr(tools_html, "run_tool", lambda args, **kw: ToolResult(0, output, "", False))
    _, executed = run_checks(make_snap("<html></html>"), 1, "standard", components=lambda name: True)
    return executed["HTM-VAL-001"]


def test_manipulated_tool_output_never_counts_as_a_clean_pass(env, monkeypatch):
    assert run_vnu(monkeypatch, env, "[" * 100_000) != "ran"  # zu tief verschachtelt für den JSON-Leser
    assert run_vnu(monkeypatch, env, "not json") == "skipped:tool_output_unreadable"
    assert run_vnu(monkeypatch, env, '{"messages": 5}') == "skipped:tool_output_unreadable"
    run_vnu(monkeypatch, env, '{"messages": [1, "x", null, {"type": "error", "url": 5}]}')  # darf nicht abstürzen


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_archive_size_and_file_count_limits(tmp_path, monkeypatch):
    bomb = tmp_path / "bomb.zip"
    write_zip(bomb, {"big.bin": b"\0" * 2_000_000})
    monkeypatch.setattr(manager, "MAX_UNPACKED", 1_000_000)
    with pytest.raises(ClaudiosError) as error:
        manager.extract(bomb, tmp_path / "out1", False)
    assert error.value.code == E.UNSAFE_ARCHIVE
    many = tmp_path / "many.zip"
    write_zip(many, {f"f{i}.txt": b"x" for i in range(20)})
    monkeypatch.setattr(manager, "MAX_UNPACKED", 10_000_000)
    monkeypatch.setattr(manager, "MAX_FILES", 10)
    with pytest.raises(ClaudiosError) as error:
        manager.extract(many, tmp_path / "out2", False)
    assert error.value.code == E.UNSAFE_ARCHIVE
    assert not (tmp_path / "out1").exists() and not (tmp_path / "out2").exists()
