"""Eigenschafts- und Stresstests für die neuen sicherheitsrelevanten Teile: tar.gz-Entpacken (nichts außerhalb des
Ziels, kein Absturz bei Unsinn), Parser der Sperrdatei-Varianten, Host-Auswertung, Zertifikatsnamen, große Eingaben."""
import io
import os
import tarfile
import time
import warnings

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from claudios.checks import quality_extra
from claudios.components import manager
from claudios.components.lock import parse_lock
from claudios.core import probe_extra
from claudios.core.errors import ClaudiosError

FAST = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
names = st.lists(st.sampled_from(["a", "b", "..", ".", "/", "\\", ":", "~", " ", "\x00", "ü"]), min_size=1, max_size=6).map("".join)


def build(path, entries):
    with tarfile.open(path, "w:gz") as tf:
        for name, kind, link in entries:
            info = tarfile.TarInfo(name)
            if kind == "sym":
                info.type, info.linkname = tarfile.SYMTYPE, link
                tf.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            else:
                data = b"x"
                info.size, info.mode = 1, 0o7777  # setuid und alles: darf nie so ankommen
                tf.addfile(info, io.BytesIO(data))


def tree(root):
    return {os.path.join(d, f) for d, _dirs, files in os.walk(root) for f in files + _dirs}


@FAST
@given(st.lists(st.tuples(names, st.sampled_from(["file", "dir", "sym"]), names), max_size=8))
def test_a_random_tar_never_writes_outside_the_target_and_never_crashes(tmp_path_factory, entries):
    base = tmp_path_factory.mktemp("t")
    archive, dest = base / "a.tar.gz", base / "out"
    dest.mkdir()
    sentinel = base / "sentinel"
    sentinel.mkdir()
    build(archive, entries)
    try:
        manager.extract(archive, dest, False)
    except ClaudiosError:
        pass  # sauber abgelehnt
    assert list(sentinel.iterdir()) == []
    assert {p for p in tree(base)} <= {str(archive), str(dest), str(sentinel)} | {p for p in tree(dest)}
    for path in tree(dest):
        resolved = os.path.realpath(path)
        assert resolved == str(dest.resolve()) or resolved.startswith(str(dest.resolve()) + os.sep)
        if os.path.isfile(path) and not os.path.islink(path):
            assert os.stat(path).st_mode & 0o7000 == 0  # kein setuid/setgid/sticky


def test_conflicting_entries_are_refused_cleanly(tmp_path):
    archive, dest = tmp_path / "a.tar.gz", tmp_path / "out"
    dest.mkdir()
    build(archive, [("a", "file", ""), ("a", "dir", "")])
    with pytest.raises(ClaudiosError):
        manager.extract(archive, dest, False)


def test_a_chain_of_links_cannot_leave_the_target(tmp_path):
    archive, dest = tmp_path / "a.tar.gz", tmp_path / "out"
    dest.mkdir()
    build(archive, [("d", "dir", ""), ("d/l1", "sym", "."), ("d/l2", "sym", "l1/../../outside")])
    with pytest.raises(ClaudiosError):
        manager.extract(archive, dest, False)


def test_a_tar_with_very_many_members_is_refused_or_finishes_quickly(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "MAX_FILES", 50)
    archive, dest = tmp_path / "a.tar.gz", tmp_path / "out"
    dest.mkdir()
    build(archive, [(f"f{i}", "file", "") for i in range(200)])
    start = time.time()
    with pytest.raises(ClaudiosError):
        manager.extract(archive, dest, False)
    assert time.time() - start < 5 and list(dest.iterdir()) == []


BASE = {"name": "x", "title": "T", "kind": "archive", "url": "https://a.example/x.zip", "sha256": "a" * 64,
        "size": 1, "license": "L", "source": "S", "exe": "x"}


@FAST
@given(st.dictionaries(st.sampled_from(["macos", "windows", "linux", ""]),
                       st.dictionaries(st.sampled_from(["url", "sha256", "exe", "size", "evil"]),
                                       st.one_of(st.text(max_size=20), st.integers(), st.none()), max_size=5),
                       max_size=3))
def test_random_variants_are_either_valid_or_refused_with_a_value_error(variants):
    try:
        parse_lock({"schema": 1, "components": [{**BASE, "variants": variants}]}, "macos")
    except (ValueError, TypeError, KeyError):
        return


@FAST
@given(st.text(max_size=300))
def test_external_hosts_survives_any_html(html):
    warnings.simplefilter("ignore")  # bs4 warnt bei Text, der wie ein Dateiname aussieht
    hosts = probe_extra.external_hosts(html, "https://example.com/", "example.com", "example.com")
    assert hosts == sorted(set(hosts)) and all("/" not in h and h != "example.com" for h in hosts)


@FAST
@given(st.lists(st.text(alphabet="abc*.-", max_size=15), max_size=6), st.text(alphabet="abc.", min_size=1, max_size=15))
def test_certificate_name_matching_never_raises_and_a_wildcard_covers_one_label_only(sans, host):
    quality_extra._covers(sans, host)
    assert quality_extra._covers(["*.example.com"], "a.example.com")
    assert not quality_extra._covers(["*.example.com"], "a.b.example.com")
    assert not quality_extra._covers(["*.example.com"], "example.com")


def test_huge_inputs_stay_fast():
    html = '<img src="https://h{0}.x.com/a.png">' * 1
    big = "".join(html.format(i) for i in range(20000))
    start = time.time()
    assert len(probe_extra.external_hosts(big, "https://example.com/", "example.com", "example.com")) == 20000
    assert time.time() - start < 10
