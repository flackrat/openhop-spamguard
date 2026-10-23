# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue. Use GitHub's private reporting:
<https://github.com/flackrat/openhop-spamguard/security/advisories/new>

Include the SpamGuard version and what you saw. I aim to reply within 7 days, to have a fix or a clear plan
within 30 days, and to credit you in the release notes if you wish.

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

The files of releases up to v6.6.2 were rebuilt from their tags and signed again on 23 October 2026, when
the repository history was tidied up. Their signatures and build attestations carry that date and name the
one-off `reissue-releases` workflow rather than the release workflow. Both commands above still check them.

## How the project is checked

Every pull request runs the tests, a privacy check, a leak check (Gitleaks) and GitHub's dependency review,
which blocks new packages with known vulnerabilities. CodeQL (extended security rules), Bandit, pip-audit on
every set of dependencies and zizmor (for the workflows themselves) run on each change and weekly. Release
files are virus-scanned with ClamAV before they are published, each Docker image is scanned with Trivy before
it is pushed, and the published image is scanned again every week.
