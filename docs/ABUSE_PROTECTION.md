# Abuse protection in CLAUDIOS

Deutsche Fassung: [ABUSE_PROTECTION.de.md](ABUSE_PROTECTION.de.md)

This document describes how CLAUDIOS prevents being used against foreign websites or the user's own network, and where these protections end. It complements [THREAT_MODEL.md](../THREAT_MODEL.md).

## Layers

| Layer | Effect | File |
|---|---|---|
| Input | One domain, HTTPS only, port 443, strict host name rules, no local suffixes, no IP addresses, Punycode. `http://` typed in the scan field becomes `https://`, nothing else is relaxed | `core/guard.py`, `ui/urlinput.py` |
| Self-declaration / level 2 | Level 1 only with the check mark. Level 2 only with a proof from the live check of the Search Console properties: valid for one host and one property, 15 minutes, one use | `core/proof.py`, `gsc/session.py` |
| Quota | Cool-down 30 s (shown as a countdown), 5 scans per hour, 5 (level 1) or 12 (level 2) per domain and day | `core/quota.py`, `core/limits.py` |
| Scan log | Hash chain plus a control value in the Windows Credential Manager. A deleted or changed log blocks scans for 24 hours | `core/audit_log.py`, `core/audit_anchor.py` |
| Gatekeeper | Every own request passes here: DNS only over DoH, all addresses must be public, connection to the verified IP, rate and size limits | `core/net.py` |
| Tools | Browser, ZAP and sslyze: total budget 1,800 s, 15 s pause between runs, at most 4 runs per kind and scan | `core/toolbudget.py`, `core/toolrunner.py` |
| DNS rebinding | The resolution is re-checked before and after the ZAP run and the Firefox/WebKit run. The Chromium run pins the target host to the verified IP. Embedded IPv4 addresses in NAT64 and 6to4 addresses are judged by the IPv4 address | `core/rebind.py`, `core/guard.py`, `checks/_browser.py` |
| Third-party hosts | Hosts that browser and ZAP resolved themselves are checked afterwards. If one points to a non-public address its data is discarded and it is reported (`BRW-FRN-001`) | `core/foreign.py` |
| Optional services | Off by default, switched on only after a confirmation, asked again before every scan. See [EXTERNAL_SERVICES.md](EXTERNAL_SERVICES.md) | `core/services.py`, `core/thirdparty.py`, `ui/expert_box.py` |

## Limits (residual risks)

- **The proof and the control value are friction, not protection against a developer.** Whoever changes the source code or deletes log and control value gets around them. A fresh installation looks the same.
- **Third-party hosts are detected, not prevented.** Chromium, Firefox, WebKit and ZAP resolve their names themselves. A change in the middle of a run is only detected afterwards; the access has then already happened.
- **In the ZAP run and the Firefox/WebKit run the target host is not pinned to the verified IP.** Only the check before and after the run applies.
- **The budget does not count the ZAP daemon itself**, only the browser script through ZAP.
- **A rejected tool run shows as `skipped:tool_failed`.** The reason (`budget`) appears only in the log.
- **Unverified on Windows:** writing the control value to the Credential Manager. The ZAP interface `core/view/hosts` was verified on Linux.

## How it is tested

The tests `test_abuse_protection.py`, `test_audit_anchor.py`, `test_rebinding.py`, `test_foreign_hosts.py` and `test_tool_budget.py` cover the layers. An allow-list in a test prevents new active checks or level-2 probes from appearing unnoticed.
