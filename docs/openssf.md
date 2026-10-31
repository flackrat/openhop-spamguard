# OpenSSF notes

Where the project stands. The badge answers themselves are the owner's to enter on [bestpractices.dev](https://www.bestpractices.dev/projects/15768).

| Area | Status |
|---|---|
| Signed releases | Done: build attestation and Sigstore signature on every file |
| Software bill of materials | Done: CycloneDX file with each release, from v6.21.0 |
| Dependency monitoring | Done: Dependabot weekly, `audit` job, dependency review on pull requests |
| Static analysis | Done: CodeQL for Python and JavaScript |
| Fuzzing | Done: `fuzz` job |
| Test coverage | Above 80% statements, reported by the `tests` job |
| Branch protection | `main` needs a pull request and passing checks |
| Governance, conduct, roadmap | [GOVERNANCE.md](../GOVERNANCE.md), [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md), [ROADMAP.md](../ROADMAP.md) |
| Security reporting | [SECURITY.md](../SECURITY.md) |
| Design and assurance | [architecture](architecture.md), [assurance case](assurance-case.md) |
| Two-factor sign-in for maintainers | Owner's account setting, not visible from the repository |
| Second maintainer | Not yet: the project has one |
