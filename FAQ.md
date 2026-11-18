# FAQ

Deutsche Fassung: [FAQ.de.md](FAQ.de.md)

## Windows warns "Windows protected your PC" (SmartScreen)
Claudios is not code-signed (certificates cost money). Compare the SHA256 checksum shown in the build log with the downloaded file, and only install files from this repository.

## My antivirus flags the program
Programs built with PyInstaller are sometimes flagged by mistake. Build it yourself from the source code if in doubt.

## Why can't I scan a site that has no HTTPS?
By design Claudios opens only HTTPS connections. A site without HTTPS cannot be checked.

## Why is a check shown as "not executed"?
A required tool is missing, a tool failed, a switch for an online service is off, or data could not be collected (for example DNS was unreachable). A check that did not run is never counted as passed. Install tools under "Components"; the page "Findings" lists every check that did not run with its reason.

## Why does "Components" show "not pinned"?
The lock files carry no checksums yet, and Claudios never installs unverified downloads. Run the lock workflows in GitHub Actions ("Werkzeug-Prüfsummen eintragen", the npm, pip and Playwright lock workflows and "Laufzeit-Sperrdatei erzeugen").

## Which Python version?
Python 3.12 or 3.13. 3.14 is not tested with the GUI library.

## Can I install sslyze from the installed program?
The built program has no Python of its own. It downloads a pinned Python runtime (embeddable, checksum in `components/runtime-lock.json`) and installs sslyze into a copy of it. This is not yet verified on real machines. Until it works, the TLS check counts as not executed.

## What is level 2?
Level 2 needs a Google sign-in and owner or full access to the domain in the Search Console. It allows active checks, up to 100 pages and Search Console data. See [docs/GOOGLE_SETUP.md](docs/GOOGLE_SETUP.md).

## Does Claudios send data to third parties?
Only to the website you check, unless you switch on an optional service on the page "External services" (domain expiry, Safe Browsing, PageSpeed). They are all off by default and each one asks before it is switched on. See [docs/EXTERNAL_SERVICES.md](docs/EXTERNAL_SERVICES.md).

## Are my scans stored?
No, unless you switch on the history on the page "Export & history" (a short summary per scan, never addresses or page content, at most 20 per domain). Screenshots are only taken if you switch that option on and stay on your computer.

## Can I scan any website?
No. Only your own or explicitly authorised sites. Scanning others without permission can be illegal. Results are technical indications, not legal advice.
