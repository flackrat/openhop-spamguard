# Test scorecard

What is tested, how much, and what is not. Figures are from the full suite run for 6.43.0 on 18 November 2026, unless a row says otherwise. All test data is made up.

| Measure | Result |
|---|---|
| Test programs in the suite | 137, all passing |
| Checks that report a count | About 2,700 (some programs report pass or fail only) |
| Statement coverage | Above 80 percent, reported by the `tests` job on every pull request |
| Spam stopped, simulated attack | Between 96.4 and 97.1 percent on each of 10 random seeds |
| Ordinary messages held by mistake | 0.9 to 1.9 percent of regulars' messages over whole runs |
| Fresh install, simulated week (6.28.0) | Monitor stops nothing; after switching to Protect on day 2, 97.5 percent of spam stopped, 1.7 to 3.2 percent of regulars' messages wrongly held, newcomers worst (harsh test, see proof) |
| Real traffic replayed | One log of 284 channel messages (3 marked spam, 11 marked fine) at all three levels: results identical to the previous version, no message marked fine held, all 3 spam caught |
| Static analysis and scans | CodeQL (Python and JavaScript), Bandit, Ruff, pip-audit, zizmor, Gitleaks, privacy check, Trivy, ClamAV |
| Fuzzing | Packet and message parsing, run by the `fuzz` job |
| Releases | Sigstore signatures, build attestation, SBOM, reproducible build check, SHA-256 checksums |

## What the tests cover

| Area | Examples |
|---|---|
| Spam detection | `redteam.py` (16 kinds of attack over simulated hours), `scenarios.py`, route and rotation tests, `teststemmem.py` |
| Not harming genuine people | `testfreespeech.py`, known people always pass, three-regular route protection, new-user cases |
| Feedback and Auto level | `testautolevel.py`, `testautoadv.py` (fake marks, a flapping suggestion, mark storms, a backwards clock, random input over simulated months) |
| Flood and airtime protection | `testfloodguard.py`, `soakfloodguard.py` |
| Web page | Browser tests for accessibility (axe), labelling, level slider, message list, map |
| Updates and installs | `testupdsh.py`, `testupdprog.py`, `testupdverify.py` (checksum checks), `testinstpw.py` (password offer) |
| Secrets and state | `testsecrets.py`, state-file loading with malformed and edited values |

## What this does not show

1. **No independent audit.** Everything above was written and run by the project itself.
2. **Not every variation.** The simulation covers many kinds of attack but not every variation, and one known gap (a very large wave of different small campaigns) is not part of the default run.
3. **Not a live adversary.** Tests use made-up traffic and replayed logs. A real attacker will find things the tests do not.
4. **One maintainer.** Review and release authority sit with one person; see [GOVERNANCE.md](../GOVERNANCE.md).
5. **Small labelled real set.** The real-traffic check rests on messages the owner marked, which is a small sample.

Found a way round SpamGuard or a flaw in the code? Please report it privately, as described in [SECURITY.md](../SECURITY.md). Method: `bash tests/run_all.sh`. Related: [proof](proof.md), [assurance case](assurance-case.md), [OpenSSF notes](openssf.md).
