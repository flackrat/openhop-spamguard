# Changelog

## v5.8.2
- Update check no longer fails when GitHub's hourly limit for your internet address is used up (60 checks an hour, shared by everyone behind the same router or mobile network): it falls back to the release page, which has no limit.
- Installer: clear messages when it isn't run with sudo, when there's no systemd (for example inside Docker), when openHop isn't a native install, and when curl (needed by the Update button) is missing.

## v5.8.1
- Web page footer: link to this repository and a short disclaimer.
- Disclaimer and privacy notes in the README and guides.
- Fix: when a duplicate-message block turned into a spam-campaign block, the first sender stayed allowed to re-send it. Campaign blocks now apply to every sender.
- Wording: blocks that last until removed now say "Stays until removed".

## v5.8
- Updates from GitHub, only when you choose: a new **Updates** section on the page shows when a new release is out and what's new, with an **Update** button. Nothing installs by itself. Settings, blocks and learnt routes are kept, and the previous version is put back automatically if the new one doesn't start.
- `update.sh` for updating (or going back to a particular release) from the command line.
- New setting Advanced > Updates > Look for new versions: once a day, or only when you press Check.

## v5.7
- `tune-openhop.sh`: the openHop speed fix (keep openHop's packet count for 60 s instead of 3 s) and an option to keep 7 days of packet history instead of 31. The installer offers both.
- The Health panel warns when an openHop upgrade has undone the speed fix.

## v5.6.1
- Fixed v5.6's packet query, which made openHop's database walk every channel message it had ever stored. SpamGuard now asks only for packets newer than the last one it saw, which openHop answers from its time index.

## v5.6
- Spam texts sent under made-up or disguised names stay blocked for 7 days (Advanced > Timing), so a returning text is stopped from its first copy.
- Lighter on openHop: SpamGuard no longer reads openHop's 500 most recent packets every few seconds.
- Replay tool: fixed undercounting of catches in long logs.

## v5.5
- Measures how far behind real time openHop's packet list is ("openHop delay" on the Health panel) and warns when it's 30 s or more.
- Every evidence-log line records how late SpamGuard saw the message.

## v5.4
- @mentions are ignored when comparing messages, so replies to the same person are never treated as a spam campaign. A campaign also needs at least two made-up, disguised or brand-new names.
- Restarts no longer log or count the same messages twice.
- The page keeps refreshing while you're typing in a box; only the sections with form controls wait.
- Warning when openHop reports no new packets for 20 minutes (radio may have stopped).
- Lower-case "l33t" names that read as a word are treated as people.

## v5.3
- Health panel, systemd watchdog (restart on hang), self-repair of openHop rules, `/health` endpoint.

## v5.2 and earlier
- Evidence log with scrambled-name export and a replay tool; emoji and look-alike handling; rotating repeater-ID protection; multi-byte path hashes; simple and Advanced views; beginner-friendly config.
