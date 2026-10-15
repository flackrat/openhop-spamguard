# Changelog

## v5.28
- **Start again from scratch now really starts the page again.** The charts, messages, activity and held list begin from the moment of the reset, and the evidence log download only includes what happened after it, so nothing from before the reset gets mixed in. Older evidence days are still deleted on their usual schedule.
- **Your own companions are never blocked.** SpamGuard reads this repeater's own companions (and room servers) from openHop, with their names and IDs, and leaves their messages out of everything it detects. Every rule it writes into openHop also skips messages the repeater sends itself, which can't be faked over the air. Someone elsewhere using the same name is still treated like anyone else. The companions it found are listed on Health (Advanced).
- **Clearer advice about openHop's rule-check bug.** As a plugin, Health now explains it as a recommendation: a known openHop bug (reported to openHop) that occasionally lets blocked spam through, fixed by one command that changes one line, keeps a backup and can be undone. The command sits in its own box with a **Copy command** button, so there's nothing to retype.
## v5.27
- **Stops one name repeating the same message over and over.** If the same name sends the same message more than three times in ten minutes, further copies of that message from that name aren't passed on for an hour. Their first copies, and anything new they say, still go out, and other people quoting it are unaffected. You can adjust or turn this off under Advanced, Duplicate suppression.
- **Quieter copy-paste guard.** SpamGuard still sets up a short guard against copies of longer messages under other names, but it no longer fills Activity and the evidence log with "Started blocking" lines for everyday chat. It only shows up when it actually stops a copy.
- A new name now needs three genuine messages, not one, before it counts as a known regular (Advanced, Known people).
## v5.26
- **Open button on openHop's Plugins page.** SpamGuard's row now has openHop's Open button, which takes you straight to SpamGuard's page on whatever port it uses. Nothing to remember or bookmark.
- **openHop's dashboard can't be replaced by mistake.** Because of that button, openHop lists SpamGuard among its web frontends. If it's picked there, SpamGuard puts openHop's own dashboard back within a minute (and at once if you're logged in), and notes it in Activity.
- **Page password in the plugin settings.** `listen_api_key` now appears in SpamGuard's Config on the Plugins page, so you can protect changes on SpamGuard's page without editing files.
- Health no longer warns about openHop's speed fix unless openHop is actually falling behind. Most repeaters keep up without it.
## v5.25
- **Reacts as soon as openHop hears a packet.** SpamGuard now listens to openHop's live packet feed and checks straight away when something arrives, instead of waiting up to three seconds for its next timed check. The timed check carries on as a backup, and if the feed isn't available SpamGuard simply works as before. It checks at most about once a second, so a busy repeater doesn't make the Pi work harder. You can turn it off under Advanced, Timing ("React as soon as openHop hears a packet"), and Health shows whether the feed is on.
- `tests/testlive.py` covers the feed, including openHop's pings and a refused token.
## v5.24
- **Moving a Docker container to the plugin now works when openHop also runs in Docker**, and when the plugin was already installed and waiting. Before, the move could wait five minutes and give up (the container carried on safely as before).
- After a reboot, the Move to the plugin button no longer stays unavailable for ten minutes if SpamGuard started before openHop. The page now says openHop isn't answering yet and checks again shortly, and pressing the button checks straight away.
- The openHop fix hint for the plugin says to run the command on whatever computer runs openHop, not only a Pi.
- Guides: the API token is under System > API Tokens in openHop's dashboard everywhere (some pages still had an older menu path).
- Tested end to end on a fresh openHop 1.1.4 on a PC: plugin install from the dashboard, upgrading a 5.21 plugin by hand, rules surviving openHop and plugin restarts, your own openHop rules left alone, the older install moved to the plugin, and Docker (SpamGuard's container, the plugin inside openHop's container, and moving between them). SpamGuard no longer appears in openHop's web frontend list.
## v5.23
- Health page, as a plugin or in Docker: "Restart if it hangs" now shows on (SpamGuard restarts itself if it gets stuck), and the systemd-only figures are hidden. The "Keep openHop's rule-check fix in place" setting is hidden where SpamGuard can't apply it.
- Guides revised after testing every install route on a fresh openHop 1.1.5: the plugin installed from openHop's dashboard, an older install moved to the plugin, and a Docker container. The README now covers the plugin way for health checks, the openHop fixes, updating, uninstalling and the replay tool, and the install steps match openHop's own buttons (System > API Tokens, then Config, Save and Enable on the Plugins page).
## v5.22
- **Plugin updates with one press.** As an openHop plugin, SpamGuard's Update button now fetches the new version, hands it to openHop and restarts on it, keeping everything it has learnt.
- **Health page fits the install.** The plugin and Docker versions no longer ask you to re-run an installer they don't have, and they restart themselves if they ever get stuck. The openHop fix messages now give the right instructions for each kind of install, and the Apply openHop fix button only appears where it works.
- **Safer plugin.** The plugin no longer has a page of its own inside openHop, so it can't be picked by mistake as openHop's main web page (which would hide openHop's dashboard). SpamGuard's page stays on its own port, 8091.
- **New installs go to the plugin.** On an openHop that can run plugins, `install.sh` now points to the plugin instead (use `--legacy` to install the older way). Updates to existing installs are unaffected.
- **Uninstalling the older install no longer touches the plugin's rules** when the plugin is the one looking after the repeater.
- If openHop's plugin manager isn't running, SpamGuard now says so plainly and how to start it; the plugin guide has the steps, plus where SpamGuard's data lives for backups.
- `tests/testpluginops.py` checks plugin updates through openHop's own plugin manager, the Health advice and the restart-if-stuck watchdog.
## v5.21
- **SpamGuard is now an openHop plugin first.** The README leads with installing it from openHop's dashboard (System > Plugins), which works however openHop is installed, on openHop 1.1.2 or later.
- **Move to the plugin.** An existing install (its own service on the Pi, or a Docker container) shows a **Move to the plugin** button on its Overview. One press installs the plugin in openHop, copies the settings and token across, hands over everything SpamGuard has learnt, and switches the old copy off once the plugin has taken over. The repeater stays protected throughout, and the page stays at the same address. If openHop is too old for plugins, the page says how to update it.
- **Only one SpamGuard per repeater.** Each copy now checks whether another is already looking after the repeater before changing anything, and waits if so, taking over by itself if the other one stops. Installing the plugin next to an older install can't make them fight, and the installer won't install over the plugin.
- Going back is easy: disable the plugin and switch the old copy on again; it takes over straight away.
- `tests/testmigrate.py` tests all of this with openHop's own plugin manager.
## v5.20
- **SpamGuard as an openHop plugin.** Each release now includes an openHop plugin file, so SpamGuard can be installed from openHop's own dashboard (System > Plugins > Install wheel), whether openHop is installed directly, in Docker, on Unraid or as a Home Assistant add-on. Paste your openHop token into the plugin's settings and enable it. Guide: `docs/openhop-plugin.md`.
- Docker: the example compose file now uses openHop's own service name (`openhop-repeater`), and the guide explains how to reach openHop from a separate compose file.
- `tests/testplugin.py` installs, starts and stops the plugin with openHop's own plugin manager.
## v5.19
- **SpamGuard now runs in Docker**, for openHop installs that run in Docker or as an Unraid app. Copy `docker-compose.example.yml`, add your openHop token and run `docker compose up -d`. Images are published for 64-bit and 32-bit Pi and for PCs on GitHub's container registry. Full guide: `docs/docker.md`.
- In Docker, settings can be given as environment variables, everything SpamGuard learns is kept in a data folder, and the Updates page shows the command to update instead of an Update button. The openHop speed and rule-check fixes aren't applied in Docker, as one container can't sensibly edit another's files.
- New `--remove-rules` option takes SpamGuard's rules back out of openHop when removing it, leaving your own rules alone.
- SpamGuard now also works with the copy of its encryption library that Debian and Ubuntu package under a different name.
- `tests/testdocker.py` checks the Docker settings.
## v5.18
- **Fewer genuine people mistaken for spammers, especially outside the UK.** Some name styles that are common on meshes in other countries were being counted as made-up, which on a busy repeater could add up to a block. Checked against thousands of real names from meshes across Europe, North America and South Africa, this cuts those false alarms by about three quarters with no change to the spam caught on real logs.
- `tests/testnames.py` keeps this checked.
## v5.17
- **Better protection against floods of junk messages.** SpamGuard now recognises a newer style of flood that sends meaningless text under a stream of made-up names, and treats it like any other spam, so the repeater it enters through gets blocked.
- Tested against a large sample of real channel traffic from a mesh that was hit by one of these floods. It picked out the flood without flagging any genuine messages, in many languages and with all sorts of emoji.
- New setting "Treat unreadable random text as spam" (Settings, Sender names), on by default. The Messages page shows the reason, and the evidence log has a `garbage` field.
- `tests/testgarbage.py` keeps this checked.
## v5.16
- **Graphs per channel.** If SpamGuard reads more than one channel (Public plus any you add on the Exceptions page), the Overview now has a "Show the graphs for" picker above the charts: All channels, or one channel at a time. The 24 hour, 7 day and time of day charts, their spoken descriptions and their "Show the numbers" tables all follow it, and each browser remembers the choice. The tiles under "Spam at a glance" still show every channel together.
- Counts per channel start from this update, since older history wasn't split by channel. Until a full week has built up, picking a channel says when its counts began and shows earlier hours as none.
- `tests/testchannels.py` and `tests/testchpick.py` check that the per-channel counts add up to the totals and that the picker works on desktop and phone.
## v5.15
- **Accessibility.** The web page now meets WCAG 2.1 AA in an automated axe-core scan of every page, in light and dark, on desktop and phone, and has been checked by hand for keyboard use.
- New **Display** page (in the menu, no Advanced needed): text size (Normal, Large, Larger), colours (same as device, light or dark), contrast (standard or high) and motion (same as device or reduce). Saved in each browser separately; nothing there changes what SpamGuard blocks.
- Keyboard: a "Skip to content" link, focus moves to the new page's heading when you change page, the phone menu takes focus when opened and gives it back when closed with Escape, and while closed its links are hidden from the keyboard and screen readers.
- Charts: each has a spoken description and a "Show the numbers" table. Spam map: circles can be reached with Tab and opened with Enter, and blocked circles have a white centre so they don't rely on red versus orange.
- Clearer colours for the amber and teal labels, stronger outlines on text boxes and switches, underlined links in text, larger tap targets on phones, labels on every form field, and error messages are announced straight away to screen readers.
- `tests/testa11y.py` keeps all of this checked.
## v5.14.4
- The evidence log now records more about each message's sender and how it was handled (`known_then` and `in_passing`), so it's easier to tell afterwards why a genuine message was held.
- `tools/fieldcheck.js` reports more about held messages, flags any message from a known person that a block stopped, flags messages you marked as not spam, and no longer counts one restart at about 02:00 (a scheduled nightly reboot) as a problem.
## v5.14.3
- The spam map is better at telling apart repeaters that share the same short route code, so spam is less likely to be pinned on an innocent repeater somewhere else.
## v5.14.2
- Fixed SpamGuard hanging after v5.14, worst on phones. Learning route codes from a week of adverts takes minutes on a Pi, and v5.14 did it while answering the web page, which also held up spam checking until the service watchdog restarted SpamGuard. Learning and the spam map are now worked out on a background thread that rests between batches, and the page shows the latest result straight away.
- Just after SpamGuard starts, the Spam sources page says it is working out the map. On a Pi the first full map takes about 10 to 15 minutes after a start.
## v5.14.1
- Fixed the Spam sources map disappearing after updating. If openHop was busy when SpamGuard started, your repeater's location didn't load and SpamGuard waited 30 minutes to try again; it now retries every minute until it has it.
- Reading the last week of adverts at start-up now works on a Pi. Asking openHop for the whole week at once took over 30 seconds and timed out, so it is now read in 12-hour slices in the background, newest first, without holding up spam checks.
## v5.14
- **Spam sources map rebuilt.** SpamGuard now learns from the adverts repeaters send, which makes the map much more accurate about where spam really enters the mesh, and much less likely to blame the wrong repeater.
- An area is only shown as sure when the evidence agrees. If the same code turns up in two separate areas, both are shown.
- The map popups say which kind each circle is, and the note under the map shows how much SpamGuard has learnt so far.
## v5.13.3
- The Spam sources map now shows only the repeaters SpamGuard is sure spam came in through. The best guesses (dashed circles) are hidden unless you turn on **Show best guesses too** above the map, and the note under the map says how many spam messages that leaves out.
- Fixed the public MeshCore map download never finishing. A handful of nodes on the public map report dates from 1970 (no clock set), and one of those stopped the whole list loading. Odd entries are now skipped one at a time.
- The public map list now only keeps repeaters on the same radio settings as yours (frequency, bandwidth and spreading factor) that have been heard from in the last 90 days, so old and out-of-band repeaters no longer get picked as a match for a route code.
## v5.13.2
- New **Clear spam history** button (Advanced > Settings, near the bottom). It empties the Overview charts, the Spam sources map and table, and the Possibly genuine list so they count again from now. Blocks, settings, known people and the evidence log are kept. Like Start again, it asks twice and needs RESET typed.

## v5.13.1
- The openHop rule-check fix is now applied automatically when SpamGuard updates or installs, with a backup of openHop's file. No command to run.
- If an openHop update removes the fix, SpamGuard notices within minutes and puts it back (openHop restarts for a few seconds). Turn this off under Advanced > Settings > Updates, "Keep openHop's rule-check fix in place".
- Health page: an **Apply openHop fix** button whenever the fix is missing.
- Once openHop releases its own fix, SpamGuard sees the fix isn't needed and leaves openHop alone; the Health page will then recommend updating openHop.

## v5.13
- **Found and fixed (optionally) an openHop bug that could let blocked spam through, or drop a genuine message.** `tune-openhop.sh` now offers a one-line fix (with backup and `--undo`); the Health panel warns when it's missing. Reported to openHop.
- **Counts now come from what openHop actually did.** SpamGuard reads openHop's record for every copy of each message (forwarded, or dropped by a rule). Spam it had a block for but openHop passed on anyway is counted as let through, and the Overview shows a notice. Before, those were counted as stopped. The evidence log records `openhop_forwarded` and `openhop_policy_dropped` for each message.
## v5.12
- **Spam sources map now shows where spam really enters the mesh.** Route codes are short and shared by many repeaters, so the old map scattered spam across the country. SpamGuard now works out the most likely real entry point, and in testing placed spam far closer to its true source than before.
- Circles with a dashed outline mean the very first repeater couldn't be identified, so the circle marks the nearest one that could. The table's "Likely repeater" column says the same.
- A notice explains when one source seems to be changing identity.
- New optional setting, **Use the public MeshCore map for repeater locations** (Advanced > Settings, off by default): once a day the Pi downloads the public MeshCore map's repeater list, so repeaters too far away for your openHop to hear can be placed too. Nothing is sent.
- Needs your repeater's location set in openHop. Spam recorded before this version has no route stored, so the map fills in as new spam arrives.
## v5.11.6
- Fix: **Reset settings to defaults** and **Start again from scratch** no longer switch the evidence log off (or change how long it's kept, or the update check). Before, a reset quietly stopped the evidence log.

## v5.11.5
- **Start again from scratch** now asks twice: after the first "are you sure", you type RESET to confirm. Nothing happens without it, even if the page is sent the request some other way.

## v5.11.4
- New **Start again from scratch** button (Advanced > Settings, at the bottom). It removes every block, including ones removed by hand, so there's no 24-hour wait, resets all settings and the sensitivity, clears trusted senders, repeaters and texts, learnt routes and known people, then starts detecting spam afresh. It keeps Monitor or Protect, channels you added, the charts and the evidence log, and relearns your regulars.
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
- Fix: fewer genuine names mistaken for disguised spam names.
## v5.10.3
- Repeater blocks now end sooner after the spam through that repeater stops (new setting: Advanced > Timing > Repeater blocks last for). On real traffic this caught the same spam and held fewer genuine people. Text blocks keep their times.
- New Possibly genuine, held panel on the main page: messages held in the last 24 hours by a repeater, link or lockdown block from names that don't look made-up, each with a Let through button that trusts the name. It only appears when there's something in it.
## v5.10.2
- Removed blocking a sender by name (added in 5.10). A repeater is shared, so a block on a person silences them for everyone downstream, invisibly, and is easy to forget. Names can also be copied, so it can hit the wrong person. SpamGuard now sticks to spam behaviour; muting a person belongs in each user's own MeshCore app. Any sender blocks already set are removed on update, with a note on the page.
- README: new section "What SpamGuard blocks, and what it doesn't".
- Includes v5.10.1: far fewer SD card writes (about 33 MB a day instead of 170 MB), and a limit on how large the known-names list can grow.
## v5.10.1
- Kinder to SD cards: SpamGuard's working file is now saved straight away only for important changes (a real block, a newly known person, anything you do on the page), otherwise at most every 5 minutes. On a day of real traffic that's 14 writes an hour instead of 72, about 33 MB a day instead of 170 MB. A clean restart or update still saves everything; a power cut loses at most 5 minutes of learning.
- Routine "copies under other names" notes no longer go to the system log. They still show on the page and in the evidence log.
- The known-names list now has a size limit.
## v5.10
- New: block a sender by name. Use Advanced > Block something yourself > Sender, or press Block sender on any message in the Advanced view. Every channel message sent under that exact name is stopped, on every channel SpamGuard reads. A blocked name is never trusted or known. Names can be changed, so this suits a regular troublemaker rather than random-name spam.
- Known people: genuine newcomers whose messages happen to pass a blocked repeater are now held for much less time.
## v5.9.1
- Known people: genuine newcomers whose messages happen to pass a blocked repeater are now held for much less time.

## v5.9
SpamGuard now learns who the regulars are, and uses openHop's policy objects to let them through while it holds strangers.

- Known people: names that send genuine messages are written into openHop as a policy object (`@spamguard.known_senders`), with a "let known people through" rule placed after your own rules.
- Repeater blocks have a new default that catches far more spam while regulars still get through. The older choices are still in Advanced.
- Links from names SpamGuard doesn't know can be held (Advanced > Known people: during campaigns / always / never).
- Lockdown button: for 30 min to 2 hours, only known names get through. It ends by itself.
- uninstall.sh also removes the known-people list from openHop.

Replaying a day of real traffic, more spam was caught and only a handful of genuine messages were held.
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
First public release of SpamGuard: spam protection for openHop MeshCore repeaters.

- Spots spam campaigns, including the usual tricks spammers use to disguise copies of a message, and writes openHop policy rules to stop your repeater passing them on.
- Duplicate-flood suppression, source-repeater blocking and protection against repeaters that keep changing their ID.
- Web page with simple and Advanced views, Monitor mode, evidence log with a replay tool, Health panel with self-repair.
- openHop speed fix (tune-openhop.sh) for small Pis where openHop falls behind.
- Updates from this repository's releases, only when you press Update on SpamGuard's page (or run update.sh). Nothing installs by itself.

Install: see the README. Changes: CHANGELOG.md.
## v5.7
- `tune-openhop.sh`: the openHop speed fix (keep openHop's packet count for 60 s instead of 3 s) and an option to keep 7 days of packet history instead of 31. The installer offers both.
- The Health panel warns when an openHop upgrade has undone the speed fix.

## v5.6.1
- Fixed v5.6's packet query, which made openHop's database walk every channel message it had ever stored. SpamGuard now asks only for packets newer than the last one it saw, which openHop answers from its time index.

## v5.6
- Spam texts that come back after a break are stopped from their first copy (Advanced > Timing).
- Lighter on openHop: SpamGuard no longer reads openHop's 500 most recent packets every few seconds.
- Replay tool: fixed undercounting of catches in long logs.

## v5.5
- Measures how far behind real time openHop's packet list is ("openHop delay" on the Health panel) and warns when it's 30 s or more.
- Every evidence-log line records how late SpamGuard saw the message.

## v5.4
- Replies to the same person are no longer mistaken for a spam campaign.
- Restarts no longer log or count the same messages twice.
- The page keeps refreshing while you're typing in a box; only the sections with form controls wait.
- Warning when openHop reports no new packets for 20 minutes (radio may have stopped).
- Fewer genuine names mistaken for made-up ones.

## v5.3
- Health panel, systemd watchdog (restart on hang), self-repair of openHop rules, `/health` endpoint.

## v5.2 and earlier
- Evidence log with scrambled-name export and a replay tool; emoji and look-alike handling; rotating repeater-ID protection; multi-byte path hashes; simple and Advanced views; beginner-friendly config.
