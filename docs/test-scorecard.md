# Test scorecard

What is tested, how much, and what is not. Figures are from the full suite run for 6.48.0 on 24 November 2026, unless a row says otherwise. All test data is made up.

| Measure | Result |
|---|---|
| Test programs in the suite | 166, all passing |
| Checks that report a count | About 4,400 (some programs report pass or fail only) |
| Statement coverage | Above 80 percent, reported by the `tests` job on every pull request |
| Spam stopped, simulated attack | Between 97.6 and 98.4 percent on each of 10 random seeds, now including hundreds of small campaigns before a flood |
| Ordinary messages held by mistake | 0.4 to 1.7 percent of regulars' messages over whole runs |
| Fresh install, simulated week (6.28.0) | Monitor stops nothing; after switching to Protect on day 2, 97.5 percent of spam stopped, 1.7 to 3.2 percent of regulars' messages wrongly held, newcomers worst (harsh test, see proof) |
| Real traffic replayed | Two recent logs (about 8,000 channel messages over 13 days) at all three levels: a little more spam caught than the previous version and no message marked fine newly held |
| Static analysis and scans | CodeQL (Python and JavaScript), Bandit, Ruff, pip-audit, zizmor, Gitleaks, privacy check, Trivy, ClamAV |
| Fuzzing | Packet and message parsing, run by the `fuzz` job |
| Releases | Sigstore signatures, build attestation, SBOM, reproducible build check, SHA-256 checksums |

## What the tests cover

| Area | Examples |
|---|---|
| Spam detection | `redteam.py` (17 kinds of attack over simulated hours), `scenarios.py`, route and rotation tests, `teststemmem.py` |
| Not harming genuine people | `testfreespeech.py`, known people always pass, three-regular route protection, new-user cases |
| Feedback and Auto level | `testautolevel.py`, `testautoadv.py` (fake marks, a flapping suggestion, mark storms, a backwards clock, random input over simulated months) |
| Flood and airtime protection | `testfloodguard.py`, `soakfloodguard.py`, `testfgflap.py` (no flapping on and off), `testsourceholds.py` |
| Web page | Browser tests for accessibility (axe), labelling, level slider, message list, map, a slow connection; `testwebpeer.py` and `testwebsocket.py` for who the page answers |
| Updates and installs | `testupdsh.py`, `testupdprog.py`, `testupdverify.py` (checksum checks), `testinstpw.py` (password offer) |
| Secrets and state | `testsecrets.py`, state-file loading with malformed and edited values |
| Rules sent to openHop | `testrulevalid.py` (a rule that could match everything is never sent), `testrulecheck.py` |

## Release test programme

What each release is checked against before it ships, and where the checks stop.

| Stage | How | Gap |
|---|---|---|
| Unit and scenario tests | Full suite on every pull request, plus the `tests` job | Made-up traffic only |
| Browser and accessibility | Playwright with axe, desktop and phone widths, light and dark | Chromium only |
| Real traffic | The owner's recent evidence logs replayed at each level, compared with the previous version | Small labelled set; floods and other packet kinds aren't in the logs |
| Network boundary | Real connections from loopback addresses, IPv4 and IPv6 where available | A real outside client can't be made in CI |
| Live repeater | Run on the maintainer's Pi before release | One repeater, one mesh |
| Experiments | Off by default; congestion holds also have a watch-only mode | Judged on live use before any becomes a default |

## What this does not show

1. **No independent audit.** Everything above was written and run by the project itself.
2. **Not every variation.** The simulation covers many kinds of attack but not every variation, and one known gap (a very large wave of different small campaigns) is not part of the default run.
3. **Not a live adversary.** Tests use made-up traffic and replayed logs. A real attacker will find things the tests do not.
4. **One maintainer.** Review and release authority sit with one person; see [GOVERNANCE.md](../GOVERNANCE.md).
5. **Small labelled real set.** The real-traffic check rests on messages the owner marked, which is a small sample.

Found a way round SpamGuard or a flaw in the code? Please report it privately, as described in [SECURITY.md](../SECURITY.md). Method: `bash tests/run_all.sh`. Related: [proof](proof.md), [assurance case](assurance-case.md), [OpenSSF notes](openssf.md).
