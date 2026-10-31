# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue. Use GitHub's private reporting:
<https://github.com/flackrat/openhop-spamguard/security/advisories/new>

Include the SpamGuard version and what you saw. I aim to reply within 7 days, to have a fix or a clear plan
within 30 days, and to credit you in the release notes if you wish.

## Ways round SpamGuard

If you find a way to get spam past SpamGuard, please report it the same private way rather than in a public
issue, so it can be fixed before it is widely known. Please don't post real spam, names or routes anywhere public.

## What SpamGuard can change on your system

It helps to know what SpamGuard is allowed to touch, both for checking it and for reporting a problem.

1. **As an openHop plugin (the recommended install),** it runs under openHop's plugin manager as openHop's own
   user, not as root. It reads packets from openHop and writes its own rules through openHop's web API, using
   the API token you give it. Its rules are all named `spamguard:...`, and it never changes your own rules.
   It writes only to its own data folder inside openHop's plugin folder. Besides channel messages, some rules
   match the kind of packet and the repeaters in its route (for a flood of requests or group data); SpamGuard
   never opens those packets.
2. **Its web page** (port 8091) shows status to anyone on your network, like openHop's own dashboard. Setting
   a page password (`listen_api_key`) protects every change, the message list and the evidence download.
   Changes are only accepted as JSON, so another website can't make them through your browser.
3. **The openHop rule-check fix** ("Keep openHop's rule-check fix in place", on by default) changes one line
   in openHop's installed files, to stop an openHop bug letting blocked spam through, and puts it back after
   an openHop update. It is applied by `tune-openhop.sh`, which you can read first, and can be turned off in
   Settings. It will be retired once openHop releases its own fix.
4. **The older direct install** (its own service, for openHop older than 1.1.2) installs two root-owned
   systemd units, `openhop-spamguard-update.path` and `openhop-spamguard-update.service`. They run
   `update.sh` as root only when you press Update. It downloads
   only from this repository's releases over HTTPS, keeps the previous version, and puts it back if the new
   one doesn't start. It doesn't yet check the release's signature itself, so please check releases by hand
   (below) if that matters to you, or use the plugin.
5. **Outside contact** is limited to GitHub (only when checking for or installing an update) and, if you turn
   it on, the public MeshCore map. There is no telemetry.

Reports about any of these are very welcome, including ones that only affect the older install.

## Supported versions

Only the latest release receives fixes. Update from the Update box in SpamGuard, or install the newest wheel
from the [releases page](https://github.com/flackrat/openhop-spamguard/releases).

## Checking a release

Each release file is signed two ways, so you can confirm it was built from this repository by its release
workflow and wasn't changed afterwards.

Build attestation (GitHub CLI):

    gh attestation verify <wheel> --repo flackrat/openhop-spamguard

Sigstore signature (cosign), using the `.sigstore.json` file next to each download:

    cosign verify-blob --bundle <file>.sigstore.json \
      --certificate-identity-regexp 'https://github.com/flackrat/openhop-spamguard/' \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com <file>

Each release also carries a software bill of materials, `spamguard-v<version>.sbom.cdx.json` (CycloneDX), signed the
same way, from v6.21.0.

The files of releases up to v6.6.2 were rebuilt from their tags and signed again on 23 October 2026, when
the repository history was tidied up. Their signatures and build attestations carry that date and name the
one-off `reissue-releases` workflow rather than the release workflow. Both commands above still check them.

Builds are reproducible: running `python3 tools/build_plugin.py` on the release's tag gives a plugin file
identical, bit for bit, to the one on the release page, and the source download is `git archive` of the tag.

## How the project is checked

Every pull request runs the tests, a privacy check, a leak check (Gitleaks) and GitHub's dependency review,
which blocks new packages with known vulnerabilities. CodeQL (extended security rules), Bandit, pip-audit on
every set of dependencies and zizmor (for the workflows themselves) run on each change and weekly. Release
files are virus-scanned with ClamAV before they are published, each Docker image is scanned with Trivy before
it is pushed, and the published image is scanned again every week.
