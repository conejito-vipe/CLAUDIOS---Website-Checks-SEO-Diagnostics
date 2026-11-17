import json
from urllib.parse import urlsplit

from claudios.checks.activechecks import KINDS
from claudios.core import probe_paths
from claudios.core.engine import run_checks
from claudios.core.errors import ClaudiosError, ErrorCode as E
from claudios.core.findings import Severity as S
from claudios.core.guard import normalize_input
from claudios.core.limits import LIMITS
from claudios.core.net import Response
from claudios.core.probes import gather_probes
from claudios.core.snapshot import Page, Snapshot
from claudios.i18n.strings import TEXTS


def make_snap(level=2):
    snap = Snapshot(target=normalize_input("example.com"), level=level, profile="standard")
    snap.pages.append(Page(url="https://example.com/", depth=1, status=200, html="<html></html>",
                           content_type="text/html"))
    snap.status = "complete"
    return snap


class FakeGK:
    cancel = None

    def __init__(self, responses=None, default=(404, "text/html", b""), fail=False):
        self.responses, self.default, self.fail, self.calls = responses or {}, default, fail, []

    async def fetch(self, url, *, method="GET", follow=True, max_bytes=None, external=False):
        assert method == "GET"
        path = urlsplit(url).path.lstrip("/")
        self.calls.append((path, follow))
        if self.fail:
            raise ClaudiosError(E.NET_CONNECT, reason="down")
        status, ctype, body = self.responses.get(path, self.default)
        return Response(url, status, {"content-type": ctype}, [], body, False, 1)


class FakeResolver:
    async def query(self, name, rtype):
        return []


def exposure(snap, level=2):
    found, executed = run_checks(snap, level, "standard")
    return [f for f in found if f.check_id == "EXP-PTH-001"], executed


async def test_exposed_files_are_found_and_their_content_is_never_stored():
    gk = FakeGK({
        ".env": (200, "text/plain", b"DB_PASSWORD=hunter2hunter2\nAPI=1\n"),
        ".git/HEAD": (200, "application/octet-stream", b"ref: refs/heads/main\n"),
        "uploads/": (200, "text/html", b"<html><title>Index of /uploads</title></html>"),
        "phpmyadmin/": (200, "text/html", b"<title>phpMyAdmin</title>"),
    })
    snap = make_snap()
    snap.extra["paths"] = await probe_paths.collect(gk, snap, None)
    assert "hunter2" not in json.dumps(snap.extra["paths"])
    found, executed = exposure(snap)
    assert sorted(f.severity for f in found) == [S.NOTE, S.WARNING, S.CRITICAL, S.CRITICAL]
    assert executed["EXP-PTH-001"] == "ran"
    assert any(f.evidence == ".env" and f.url == "https://example.com/.env" for f in found)
    assert all("hunter2" not in f.msg_en + f.msg_de + f.evidence for f in found)
    assert len(gk.calls) == len(probe_paths.PATHS)
    assert all(follow is False for _path, follow in gk.calls)
    assert {path for path, _f in gk.calls} == {p[0] for p in probe_paths.PATHS}


async def test_sites_that_answer_everything_with_200_cause_no_false_alarm():
    page = b"<html><title>Welcome</title>\nFOO=bar\n</html>"
    snap = make_snap()
    snap.extra["paths"] = await probe_paths.collect(FakeGK(default=(200, "text/html; charset=utf-8", page)), snap, None)
    found, executed = exposure(snap)
    assert found == [] and executed["EXP-PTH-001"] == "ran"


async def test_unreachable_server_is_never_reported_as_passed():
    snap = make_snap()
    snap.extra["paths"] = await probe_paths.collect(FakeGK(fail=True), snap, None)
    found, executed = exposure(snap)
    assert found == [] and executed["EXP-PTH-001"] == "skipped:paths_unreachable"
    _, executed = exposure(make_snap())
    assert executed["EXP-PTH-001"] == "skipped:no_path_data"


async def test_the_probe_and_the_check_only_run_at_level_2():
    snap1 = make_snap(level=1)
    gk1 = FakeGK()
    await gather_probes(gk1, snap1, FakeResolver())
    assert "paths" not in snap1.extra and not any(path == ".git/HEAD" for path, _f in gk1.calls)
    _, executed = exposure(snap1, level=1)
    assert executed["EXP-PTH-001"] == "skipped:level2_required"

    snap2, seen = make_snap(level=2), []
    gk2 = FakeGK()
    await gather_probes(gk2, snap2, FakeResolver(), progress=lambda stage, cur, total: seen.append((stage, cur, total)))
    assert "paths" in snap2.extra and seen[-1] == ("probe:paths", 9, 9)
    assert any(path == ".git/HEAD" for path, _f in gk2.calls)


def test_path_list_invariants_and_texts():
    paths = [p[0] for p in probe_paths.PATHS]
    assert len(paths) <= LIMITS.active_paths_max and len(set(paths)) == len(paths)
    assert all(not p.startswith("/") and ".." not in p and "?" not in p for p in paths)
    assert {p[1] for p in probe_paths.PATHS} <= set(KINDS)
    for lang in ("de", "en"):
        assert TEXTS[lang]["probe.paths"].strip()
    assert set(TEXTS["de"]) == set(TEXTS["en"])
