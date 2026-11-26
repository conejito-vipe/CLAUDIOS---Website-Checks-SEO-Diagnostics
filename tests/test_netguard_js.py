"""Schutz der Browser-Skripte vor lokalen und privaten Zielen: Namen, Adressen, DNS-Auflösung; in allen vier Skripten identisch."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NPM = Path(__file__).resolve().parent.parent / "src" / "claudios" / "components" / "npm"
SCRIPTS = ("browser_probe.js", "engine_probe.js", "shot_probe.js", "zap_probe.js")
NODE = shutil.which("node")


def block(name: str) -> str:
    text = (NPM / name).read_text("utf-8").replace("\r\n", "\n")
    start = text.index("// BEGIN-NETGUARD")
    return text[start:text.index("// END-NETGUARD") + len("// END-NETGUARD")]


def test_the_guard_is_identical_in_all_browser_scripts_and_used_for_every_request():
    assert len({block(n) for n in SCRIPTS}) == 1
    for name in SCRIPTS:
        text = (NPM / name).read_text("utf-8")
        assert 'await blockedHost(host)' in text and "isLocalName(host))" not in text, name


def run_js(expression: str):
    code = ('const input = {host: "pinned.example.com"};\n' + block("browser_probe.js") + "\nconsole.log(JSON.stringify(" + expression + "));")
    out = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(NODE is None, reason="node fehlt")
def test_local_and_internal_names_are_blocked_even_with_tricks():
    hosts = ["localhost", "localhost.", "LOCALHOST", "foo.localhost", "router.home.arpa", "printer.lan", "nas.local", "x.internal",
             "intranet", "127.0.0.1", "[::1]", "[::ffff:7f00:1]", "10.0.0.5", "", "wiki.corp"]
    assert run_js(json.dumps(hosts) + ".map(isLocalName)") == [True] * len(hosts)


@pytest.mark.skipif(NODE is None, reason="node fehlt")
def test_public_names_stay_reachable():
    hosts = ["example.com", "www.example.co.uk", "cdn.example.org", "fonts.gstatic.com", "xn--bcher-kva.example"]
    assert run_js(json.dumps(hosts) + ".map(isLocalName)") == [False] * len(hosts)


@pytest.mark.skipif(NODE is None, reason="node fehlt")
def test_private_addresses_are_recognised_and_public_ones_are_not():
    private = ["127.0.0.1", "10.1.2.3", "172.16.0.1", "172.31.255.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0",
               "::1", "::", "fe80::1", "fd12::1", "fc00::1", "::ffff:10.0.0.1", "224.0.0.1"]
    public = ["8.8.8.8", "93.184.216.34", "172.32.0.1", "172.15.0.1", "100.63.0.1", "2606:4700::1111"]
    assert run_js(json.dumps(private) + ".map(privateIp)") == [True] * len(private)
    assert run_js(json.dumps(public) + ".map(privateIp)") == [False] * len(public)


@pytest.mark.skipif(NODE is None, reason="node fehlt")
def test_names_resolving_privately_are_blocked_but_the_pinned_target_host_is_not_looked_up():
    code = ('const input = {host: "pinned.example.com"};\n' + block("browser_probe.js") + '''
dns.lookup = async (host) => (host === "evil.example.net" ? [{address: "192.168.1.1"}] : [{address: "93.184.216.34"}]);
(async () => console.log(JSON.stringify([await blockedHost("evil.example.net"), await blockedHost("good.example.net"),
  await blockedHost("pinned.example.com")])))();''')
    out = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30, check=True).stdout
    assert json.loads(out) == [True, False, False]
