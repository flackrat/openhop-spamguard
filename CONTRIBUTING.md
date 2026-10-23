# Contributing to SpamGuard

Thank you for helping. SpamGuard is a small project, so the process is simple.

## Reporting a bug or suggesting something

Open an issue using the templates at <https://github.com/flackrat/openhop-spamguard/issues/new/choose>.
For a bug, say which SpamGuard version you run (shown on the Overview page) and how it is installed
(openHop plugin, normal install or Docker). The Evidence log, if you have it switched on, helps a lot, but remove
channel names and keys before sharing it. Security problems go through private reporting, see `SECURITY.md`.

## Sending a change

1. Fork the repository and make your change on a branch.
2. Run the whole test suite with `bash tests/run_all.sh` (about 3 minutes). Nothing in it talks to a real repeater.
3. Open a pull request against `main`. Describe what changed and why, and mention how you tested it.

The same suite runs on GitHub for every pull request, together with CodeQL and a Bandit and pip-audit check.
Changes to `main` can only be made through a pull request, and the `tests` check has to pass before GitHub
allows the merge. The same applies to the maintainer.

## What a good change looks like

1. **Tests come with the change.** A new feature or a fixed bug gets a check in `tests/` (add it to the list in
   `tests/run_all.sh` if it is a new file). Bug fixes should include a test that fails without the fix.
2. **Follow the style already in `spamguard.py`:** plain Python with type hints on new functions, short
   docstrings that say why, no new dependencies unless there is a strong reason (the plugin installs on a
   Raspberry Pi 3).
3. **Words shown to people are plain and brief.** Many readers use a phone, and many are not technical.
4. **Add a line to `CHANGELOG.md`** under the next version.
5. **Detection stays behavioural.** SpamGuard blocks spam behaviour, never people or opinions, and never touches
   direct messages or acknowledgements.

## Keep it free of personal details

Never commit real names, messages, places, coordinates, addresses, callsigns or anything copied from a real
mesh conversation, including in tests, comments and examples. Make up every example. The Tests check runs a
privacy check (`tools/privacy_check.py`) and a leak check (Gitleaks) on each pull request, and a pull request
can't be merged until both pass. If a made-up value is flagged, add it to `.privacy-allow`. To run the check
yourself before committing:

    python3 tools/privacy_check.py --staged

## Licence

SpamGuard is released under the GNU AGPL version 3. By sending a change you agree that it is released under the
same licence.
