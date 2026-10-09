# Changelog

## v5.11.5
- **Start again from scratch** now asks twice: after the first "are you sure", you type RESET to confirm. Nothing happens without it, even if the page is sent the request some other way.

## v5.11.4
- New **Start again from scratch** button (Advanced > Settings, at the bottom). It removes every block, including ones removed by hand, so there's no 24-hour wait, resets all settings and the sensitivity, clears trusted senders, repeaters and texts, learnt routes and known people, then starts detecting spam afresh. It keeps Monitor or Protect, channels you added, the charts and the evidence log, and relearns regulars from the last day's normal-looking names.
- The old "Reset all to defaults" button is now **Reset settings to defaults**, as it only ever reset settings.
- Removing a block now says how to undo the 24-hour wait (Exceptions > Not re-blocked > Clear).

## v5.11.3
- Each release now includes its own download file, and the Update button fetches that (falling back to GitHub's automatic archive as before). GitHub counts downloads of release files, which gives a rough idea of how many repeaters install each update. SpamGuard sends nothing extra: the Pi already fetches the update from GitHub when you press Update, and no identifying information is added.

## v5.11.2
- The Overview now shows when an update is ready to install, with **What's new** and **Update now**, instead of only in the Updates page. It also says when an update is under way, or if the last one didn't finish.
- Releases are now published automatically when a new version is pushed.

## v5.11.1
- Phones: the map no longer shows on top of the menu and the top bar.
- Phones: the **Advanced** switch is now at the top of the menu, so it can't end up hidden behind the browser's toolbar. The top bar shows "Advanced" while it's on, and switching it leaves the menu open so you can see the extra pages appear.
- Phones: the page behind the open menu no longer scrolls; tapping the page you're already on, or pressing Escape, closes the menu.
- Spam sources map: it no longer jumps back to its starting view or closes an open label every time the page refreshes.

## v5.11
- New menu, laid out like openHop's own: Overview, Protection, Monitoring and System, with a slide-out menu on phones. Each area has its own page instead of one long page.
- Long lists (messages, blocks, activity, possibly genuine) show 10 at a time with **Show more / Show all**.
- Overview numbers and charts: spam stopped, let through, spam's share of channel traffic, airtime saved (from your radio settings), genuine messages held and known people; last 24 hours, last 7 days and spam by hour of day.
- **Spam sources** page: which repeaters spam arrives through, on a map using the locations repeaters advertise in openHop, plus a table with Block / Never block. The map needs internet on the viewing device; the table doesn't.
- Fix: names with a decorative symbol inside them (for example a cross or emoji between letters) are no longer treated as disguised spam names.

## v5.10.3
- Repeater blocks now end 2 hours after the spam through that repeater stops, instead of 6 (new setting Advanced > Timing > Repeater blocks last for). On 38 hours of real traffic this caught the same spam and held fewer genuine people. Text blocks keep their times.
- New **Possibly genuine, held** panel on the main page: messages held in the last 24 hours by a repeater, link or lockdown block from names that don't look made-up, each with a **Let through** button that trusts the name. It only appears when there's something in it.

## v5.10.2
- Removed blocking a sender by name (added in 5.10). A repeater is shared, so a block on a person silences them for everyone downstream, invisibly, and is easy to forget; names can also be copied, so it can hit the wrong person. SpamGuard now sticks to spam behaviour; muting a person belongs in each user's own MeshCore app. Any sender blocks already set are removed on update, with a note on the page.
- README: new section "What SpamGuard blocks, and what it doesn't".

## v5.10.1
- Kinder to SD cards: SpamGuard's working file is now saved straight away only for important changes (a real block, a newly known person, anything you do on the page), otherwise at most every 5 minutes. On a day of real traffic that's 14 writes an hour instead of 72, about 33 MB a day instead of 170 MB. A clean restart or update still saves everything; a power cut loses at most 5 minutes of learning.
- Routine "copies under other names" notes no longer go to the system log (they still show on the page and in the evidence log).
- The known-names list is capped at the 5,000 most recently heard.

## v5.10
- Block a sender by name: Advanced > Block something yourself > Sender, or **Block sender** on any message (Advanced view). Stops every channel message sent under that exact name, on every channel SpamGuard reads. A blocked name is never trusted or known. Names can be changed, so this suits a regular troublemaker rather than random-name spam.
- Includes v5.9.1.

## v5.9.1
- Known people: a genuine message that only passes *through* a blocked repeater partway along its route now counts towards its sender becoming known. Spam starts at the blocked repeater itself, so messages starting there still never count. Before, a newcomer whose only route went through the blocked repeater stayed held for as long as the block lasted; now only their first message is held.

## v5.9
- Known people: SpamGuard learns names that send genuine messages and writes them into openHop as a policy object (`@spamguard.known_senders`), with a "let known people through" rule placed after your own rules.
- Repeater blocks now default to "Anything passing through, except people it knows". On real logs the spammer used a new full route for every message, so "Routes starting there" never matched; the new mode caught every one while letting regulars through. Existing choices remain in Advanced.
- Links from names SpamGuard doesn't know are held while a spam campaign is under way (Advanced > Known people: always / during campaigns / never).
- Lockdown button: for 30 min to 2 hours, only known names get through on the channels SpamGuard reads. Ends by itself.
- After updating, the known list starts from the names heard in the last day.
- The evidence log records whether each sender was known.
- `uninstall.sh` also removes the known-people list from openHop.

## v5.8.3
- `uninstall.sh`: removes SpamGuard cleanly, including taking its rules back out of openHop. Your own openHop rules and settings are left alone. Options `--keep-evidence` and `--undo-speed-fix`.
- README and guide: an Uninstall section.

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
