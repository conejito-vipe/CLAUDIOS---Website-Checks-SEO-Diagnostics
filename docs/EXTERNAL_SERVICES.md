# External services in Claudios

Deutsche Fassung: [EXTERNAL_SERVICES.de.md](EXTERNAL_SERVICES.de.md)

Claudios talks only to the website you check. Services that send data to third parties are **off by default** and can be switched on one by one on the page "External services" (each with a confirmation). The switch is stored in `config/services.json` (only "service: on/off", no keys, no addresses). Local options (screenshots) are stored in `config/options.json`.

| Service | Where | What is sent | What the third party sees |
|---|---|---|---|
| RDAP (domain expiry) | `data.iana.org`, then the RDAP server of the top-level domain | the registrable domain | IP address, user agent |
| Safe Browsing | `safebrowsing.googleapis.com` | up to 5 addresses of the website without parameters, plus your API key | IP address, the addresses |
| PageSpeed Insights | `www.googleapis.com` | the address of the home page | IP address; Google fetches the page itself |

## Protection

- **RDAP** runs through the gatekeeper (`external=True`): DNS over DoH, only public addresses, connection to the verified IP, rate and size limit.
- **Safe Browsing and PageSpeed** run through `core/thirdparty.py`. This is a deliberate exception: the gatekeeper can only do GET and has a 15-second timeout. The client reaches only the two fixed hosts above, only HTTPS on port 443, follows no redirect, ignores environment proxies and limits the response size. The system resolves the names, not DoH (as with the Google sign-in).
- **The API key** for Safe Browsing is kept in the Windows Credential Manager, never in a file, never in the report and never in the log. On other systems it lives in memory only.
- **Without the switch** no request leaves the computer, and the matching check counts as not executed (`skipped:..._disabled`), never as passed.

## Screenshots (local)

A dedicated browser script (`shot_probe.js`) opens the home page with the same rules as the browser run (target host pinned to the verified IP, no HTTP, no local addresses, no service workers) and saves two images in the cache folder. The last three scans are kept. The images are not checked for secrets, they show what a visitor sees. The run counts towards the tool budget (`core/toolbudget.py`).

## Unverified

Format of the IANA list and of the RDAP answers, the Safe Browsing endpoint (v4 `threatMatches:find` with `?key=`), the answer fields of PageSpeed (`lighthouseResult`, `loadingExperience`) and the behaviour of `shot_probe.js` with a real Chromium were written from memory. If they differ, the check counts as not executed, never as passed.
