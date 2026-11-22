"""Update-Prüfung: Versionsvergleich, Auswahl des Releases, Download mit Prüfsumme (ohne Netz)."""
import hashlib
import json

import httpx
import pytest

from claudios.core import updater
from claudios.core.errors import ClaudiosError, ErrorCode as E

BASE = "https://github.com/x/y/releases/download/v0.2.0/"
SETUP = b"installer-bytes"
DIGEST = hashlib.sha256(SETUP).hexdigest()


def release(**changes):
    data = {"tag_name": "v0.2.0", "draft": False, "prerelease": False,
            "html_url": "https://github.com/x/y/releases/tag/v0.2.0",
            "assets": [{"name": "CLAUDIOS-Setup-0.2.0.exe", "browser_download_url": BASE + "CLAUDIOS-Setup-0.2.0.exe"},
                       {"name": "CLAUDIOS-Setup-0.2.0.exe.sha256",
                        "browser_download_url": BASE + "CLAUDIOS-Setup-0.2.0.exe.sha256"}]}
    data.update(changes)
    return data


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_versions_are_compared_numerically():
    assert updater.is_newer("v0.2.0", "0.1.0") and updater.is_newer("0.1.10", "0.1.9") and updater.is_newer("1.0", "0.9.9")
    assert not updater.is_newer("0.1.0", "0.1.0") and not updater.is_newer("0.1", "0.1.0")
    assert not updater.is_newer("abc", "0.1.0") and not updater.is_newer("0.2.0", "kaputt")


def test_only_a_complete_published_release_with_trusted_hosts_is_accepted():
    info = updater.pick_release(release())
    assert info is not None and info.version == "0.2.0" and info.installer_name == "CLAUDIOS-Setup-0.2.0.exe"
    assert updater.pick_release(release(draft=True)) is None
    assert updater.pick_release(release(prerelease=True)) is None
    assert updater.pick_release(release(tag_name="neu")) is None
    assert updater.pick_release(release(assets=[])) is None
    evil = release()
    evil["assets"][0]["browser_download_url"] = "https://evil.test/CLAUDIOS-Setup-0.2.0.exe"
    assert updater.pick_release(evil) is None
    wrong = release()
    wrong["assets"][0]["name"] = "setup.exe"
    assert updater.pick_release(wrong) is None
    assert updater.pick_release("kein dict") is None


def test_the_checksum_is_read_from_the_file():
    assert updater.parse_sha256(f"{DIGEST.upper()}  CLAUDIOS-Setup-0.2.0.exe\n") == DIGEST
    assert updater.parse_sha256("nichts") == ""


def test_fetch_latest_reads_the_api_and_treats_404_as_no_release():
    def ok(request):
        assert request.url.host == "api.github.com"
        return httpx.Response(200, content=json.dumps(release()).encode())

    assert updater.fetch_latest(client(ok)).version == "0.2.0"
    assert updater.fetch_latest(client(lambda request: httpx.Response(404))) is None
    assert updater.fetch_latest(client(lambda request: httpx.Response(200, content=b"kein json"))) is None
    with pytest.raises(ClaudiosError):
        updater.fetch_latest(client(lambda request: httpx.Response(500)))


def _handler(sha_text):
    def handler(request):
        if request.url.path.endswith(".sha256"):
            return httpx.Response(200, text=sha_text)
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"location": "https://objects.githubusercontent.com/file"})
        return httpx.Response(200, content=SETUP)

    return handler


def test_the_installer_is_downloaded_and_verified(tmp_path):
    info = updater.pick_release(release())
    path = updater.download_installer(info, tmp_path, client=client(_handler(f"{DIGEST}  x.exe")))
    assert path.read_bytes() == SETUP


def test_a_wrong_checksum_leaves_no_file_behind(tmp_path):
    info = updater.pick_release(release())
    with pytest.raises(ClaudiosError) as error:
        updater.download_installer(info, tmp_path, client=client(_handler("0" * 64)))
    assert error.value.code == E.CHECKSUM_MISMATCH and not list(tmp_path.iterdir())


def test_a_redirect_to_a_foreign_host_is_refused(tmp_path):
    info = updater.pick_release(release())

    def handler(request):
        if request.url.path.endswith(".sha256"):
            return httpx.Response(200, text=DIGEST)
        return httpx.Response(302, headers={"location": "https://evil.test/x"})

    with pytest.raises(ClaudiosError) as error:
        updater.download_installer(info, tmp_path, client=client(handler))
    assert error.value.code == E.DOWNLOAD_FAILED and not list(tmp_path.iterdir())
