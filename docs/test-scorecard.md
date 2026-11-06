# Test scorecard

What is tested, how much, and what is not. Figures are from the full suite run for 6.28.0 on 6 November 2026. All test data is made up.

| Measure | Result |
|---|---|
| Test programs in the suite | 105, all passing |
| Checks that report a count | 1,910 across 93 of those programs (the rest report pass or fail only) |
| Statement coverage | Above 80 percent, reported by the `tests` job on every pull request |
| Spam stopped, simulated attack | 96.6 percent of about 11,760 spam messages over 10 random seeds, every run between 96.4 and 96.9 |
| Ordinary messages held by mistake | 2.7 percent during attack hours, 0.8 percent of regulars over whole runs |
| Real traffic replayed | 3 days at Balanced: 2 of 23 messages marked fine were held, neither from a new person |
| Static analysis and scans | CodeQL (Python and JavaScript), Bandit, Ruff, pip-audit, zizmor, Gitleaks, privacy check, Trivy, ClamAV |
| Fuzzing | Packet and message parsing, run by the `fuzz` job |
| Releases | Sigstore signatures, build attestation, SBOM, reproducible build check, SHA-256 checksums |

## What the tests cover

| Area | Examples |
|---|---|
| Spam detection | `redteam.py` (14 kinds of attack over simulated hours), `scenarios.py`, route and rotation tests, `teststemmem.py` |
| Not harming genuine people | `testfreespeech.py`, known people always pass, three-regular route protection, new-user cases |
| Feedback and Auto level | `testautolevel.py`, `testautoadv.py` (fake marks, a flapping suggestion, mark storms, a backwards clock, random input over simulated months) |
| Flood and airtime protection | `testfloodguard.py`, `soakfloodguard.py` |
| Web page | Browser tests for accessibility (axe), labelling, level slider, message list, map |
| Updates and installs | `testupdsh.py`, `testupdprog.py`, `testupdverify.py` (checksum checks), `testinstpw.py` (password offer) |
| Secrets and state | `testsecrets.py`, state-file loading with malformed and edited values |

## What this does not show

1. **No independent audit.** Everything above was written and run by the project itself.
2. **Not a live adversary.** Tests use made-up traffic and replayed logs. A real attacker will find things the tests do not.
3. **One maintainer.** Review and release authority sit with one person; see [GOVERNANCE.md](../GOVERNANCE.md).
4. **Small labelled real set.** The real-traffic check rests on messages the owner marked, which is a small sample.

Found a way round SpamGuard or a flaw in the code? Please report it privately, as described in [SECURITY.md](../SECURITY.md). Method: `bash tests/run_all.sh`. Related: [proof](proof.md), [assurance case](assurance-case.md), [OpenSSF notes](openssf.md).
