# Contributing to SpamGuard

Thank you for helping. SpamGuard is a small project, so the process is simple.

## Reporting a bug or suggesting something

Open an issue using the templates at <https://github.com/flackrat/openhop-spamguard/issues/new/choose>.
For a bug, say which SpamGuard version you run (shown on the Overview page) and how it is installed
(openHop plugin, normal install or Docker). The Evidence log, if you have it switched on, helps a lot, but remove
channel names and keys before sharing it. Security problems go through private reporting, see `SECURITY.md`.

## Other ways to help

You don't need to write code to help:

1. **Run it in Monitor on your repeater** and report anything it would have stopped that wasn't spam, or spam
   it missed. The Spam and Fine labels on the Messages page record this for you.
2. **Suggest plainer wording** for anything on the page that's confusing.
3. **Share what spam looks like on your mesh,** with every name and message made up, so new kinds can be caught.

For anything bigger than a small fix, please open an issue first to talk it through, so your time isn't wasted.

## Sending a change

1. Fork the repository and make your change on a branch.
2. Run the whole test suite with `bash tests/run_all.sh` (about 3 minutes). Nothing in it talks to a real repeater.
   Check the coding standard with `ruff check .` (the rules are in `ruff.toml`).
3. Open a pull request against `main`. Describe what changed and why, and mention how you tested it.

The same suite runs on GitHub for every pull request, under coverage (the shipped code should stay at 80% or
more), together with the coding standard, the privacy and leak checks, dependency review, CodeQL, Bandit,
pip-audit and zizmor.
Changes to `main` can only be made through a pull request, and the `tests` check has to pass before GitHub
allows the merge. The same applies to the maintainer.

## What a good change looks like

1. **Tests come with the change.** A new feature or a fixed bug gets a check in `tests/` (add it to the list in
   `tests/run_all.sh` if it is a new file). Bug fixes should include a test that fails without the fix.
2. **Follow the style already in `spamguard.py`:** plain Python with type hints on new functions, short
   docstrings that say why, no new dependencies unless there is a strong reason (the plugin installs on a
   Raspberry Pi 3).
3. **Words are plain and brief**, on the page, in settings, in Activity and in the docs: one or two short sentences,
   with the detail in `docs/` rather than on the page. Many readers use a phone, and many are not technical.
4. **Add a line to `CHANGELOG.md`** under the next version.
5. **Detection stays behavioural.** SpamGuard blocks spam behaviour, never people or opinions, and never touches
   direct messages or acknowledgements.

## Keep it free of personal details

Never commit real names, messages, places, coordinates, addresses, callsigns or anything copied from a real
mesh conversation, including in tests, comments and examples. Make up every example. The Tests check runs a
privacy check (`tools/privacy_check.py`) and a leak check (Gitleaks) on each pull request, and a pull request
can't be merged until both pass. If a made-up value is flagged, add it to `.privacy-allow`. A third check,
Microsoft Presidio (`tools/presidio_check.py`), points out new names and places in the added lines. It only
warns, because it guesses: if what it points at is made up, leave it. To run the check
yourself before committing:

    python3 tools/privacy_check.py --staged

## Licence

SpamGuard is released under the GNU AGPL version 3. By sending a change you agree that it is released under the
same licence.
