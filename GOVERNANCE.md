# How SpamGuard is run

## Governance model

SpamGuard is a small project with one maintainer, who makes the final decision on what goes in and when it
is released. Decisions are made in the open: suggestions and bug reports come in as GitHub issues, every
change goes through a pull request, and the reasons for decisions are written in the pull request, the
changelog or the documentation. Anyone can propose a change; good ideas from users and testers have shaped
most releases.

Two principles decide most questions:

1. **SpamGuard blocks spam behaviour, never people or opinions.** It never filters what people say, never
   touches direct messages or acknowledgements, and never reports back to anyone.
2. **Privacy first.** Nothing from real mesh traffic ever goes into the repository (see
   [CONTRIBUTING.md](CONTRIBUTING.md)).

## Roles and responsibilities

| Role | Who | Responsibilities |
|------|-----|------------------|
| Maintainer | [@flackrat](https://github.com/flackrat) | Reviews and merges changes, makes releases, answers security reports, keeps the dependencies and checks up to date, and enforces the [code of conduct](CODE_OF_CONDUCT.md). |
| Contributors | Anyone | Report bugs, suggest features, test releases and send pull requests, following [CONTRIBUTING.md](CONTRIBUTING.md). |
| Security reporters | Anyone | Report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md). They are credited in the release notes if they wish. |

The maintainer is responsible for:

1. **Releases:** only from `main`, built, virus-scanned and signed by the release workflow, with notes from
   [CHANGELOG.md](CHANGELOG.md).
2. **Security:** replying to reports within 7 days and fixing or giving a clear plan within 30 days
   ([SECURITY.md](SECURITY.md)).
3. **Quality:** every change must pass the required checks (tests, coding standard, privacy, leak and
   dependency checks) before it can be merged. Nobody, including the maintainer, can push to `main`
   directly or move a release tag.

## Continuity

The project is set up so that it doesn't depend on any one machine or private copy: the code, the release
process, the signing (keyless, through GitHub Actions) and the documentation all live in this repository.
A second person has access to the repository and has agreed to take over if the maintainer can't
continue. They can open and close issues, review and merge pull requests, and make a release, which the
release workflow builds, virus-scans and signs by itself when a new version reaches `main`. Signing is
keyless, so there are no keys or passwords to hand over. The project can therefore carry on within a week
of losing any one person.

## Changing this document

Changes to how the project is run go through a pull request like any other change.
