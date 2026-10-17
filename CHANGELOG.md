# Changelog

SpamGuard and FloodGuard ship together as one openHop plugin with one release number (SpamGuard's), but each has its own history below. FloodGuard's version only goes up when FloodGuard itself changes.

## v6.3 (FloodGuard 1.1, unchanged)
### SpamGuard 6.3
- **Replay guard: old messages sent again.** Some devices pick up channel messages and send them out again later, with their own clock (in one case measured on a Dutch mesh, about 823 days slow) and sometimes with the sender's name cut short, so one message arrives many times over. When a message turns up again that was first heard at least half a minute earlier, under the same name with a badly wrong clock or under a cut-short copy of the name, further copies of it from that name are held back for six hours. The original always went out first, the same text from anyone else is untouched, and anything new from that name still goes out.
- A person re-sending their own message isn't caught (their device gives it a new, correct time and their full name), nor are the mesh's own echoes seconds apart, nor short replies like "ok thanks".
- Replayed copies don't count towards SpamGuard getting to know a name, so a replaying device can't make names "known".
- On by default; Advanced, Settings, Duplicate suppression turns it off. Its blocks show on the Blocks page marked *replay*, and in openHop as *(replayed)*.
- `tests/testreplay.py` covers it.

## v6.2 (FloodGuard 1.1, unchanged)
### SpamGuard 6.2
- **Don't repeat wardriving pings** (Channels page, off by default). Wardriving apps such as MeshMapper send a ping with the phone's GPS position on `#wardriving` and log every repeater that echoes it, which maps precisely where each repeater can be heard. When on, this repeater still hears the pings but doesn't pass them on, so it isn't logged. Other channels, direct messages, adverts and path searches are untouched, and pings from this repeater's own companions still go out. The Channels page shows how many pings were heard and not repeated. More wardriving channels can be added by name or key (Advanced, Settings, Privacy).
- If another channel openHop reads happens to share the wardriving channel's one-byte code, only messages that look like MeshMapper pings are held back on it, so chat there is never caught.
- It's a privacy choice, so it's kept through Start again from scratch and is never part of a settings profile.
- The trade-off is that the repeater drops off community coverage maps. It doesn't hide the repeater from direction-finding (fox hunting), its own adverts or route logs; the Help page explains.
- **FloodGuard has its own version number,** shown next to its name in the menu, at the bottom of every page and on the FloodGuard page. Bug reports ask for both.
- Fixed: saving a list setting (such as extra name patterns) could fail while writing its Activity note.
- `tests/testwardrive.py` checks it against openHop's rule engine.

## v6.2
- **Don't repeat wardriving pings** (Channels page, off by default). Wardriving apps such as MeshMapper send a ping with the phone's GPS position on `#wardriving` and log every repeater that echoes it, which maps precisely where each repeater can be heard. When on, this repeater still hears the pings but doesn't pass them on, so it isn't logged. Other channels, direct messages, adverts and path searches are untouched, and pings from this repeater's own companions still go out. The Channels page shows how many pings were heard and not repeated. More wardriving channels can be added by name or key (Advanced, Settings, Privacy).
- If another channel openHop reads happens to share the wardriving channel's one-byte code, only messages that look like MeshMapper pings are held back on it, so chat there is never caught.
- It's a privacy choice, so it's kept through Start again from scratch and is never part of a settings profile.
- The trade-off is that the repeater drops off community coverage maps. It doesn't hide the repeater from direction-finding (fox hunting), its own adverts or route logs; the Help page explains.
- Fixed: saving a list setting (such as extra name patterns) could fail while writing its Activity note.
- `tests/testwardrive.py` checks it against openHop's rule engine.

## v6.1 (FloodGuard 1.1)
### FloodGuard 1.1: learns your mesh
- **On by default, learning first.** FloodGuard is now on for every repeater, but it spends its first three days learning: how busy this repeater's radio normally gets, and how far flood packets and adverts normally travel. Meanwhile it only counts what it would stop, even in Protect, and the FloodGuard page shows "Learning, day 1 of 3". Activity says when it starts and when it begins acting. **Start protecting now** skips the wait.
- **Sets its own limits, and keeps them in step.** After learning it sets the level it steps in at (about twice a normal busy hour, and above the busiest genuine five minutes), the hop limit for unscoped flood packets (about twice the longest normal routes, 16 to 32 hops) and the hop limit for adverts (just past the furthest normal adverts, 6 to 16 hops). It checks them once a day against the last week of calm traffic and moves them a little at a time. Hours with a flood in them are never learnt from.
- **Your values win.** A setting you change yourself is never touched again; **Back to automatic** hands it back. **Reset and learn again** puts every FloodGuard setting back to its own values and learns from scratch for three days, protecting with the recommended values meanwhile.
- **Off switch on the FloodGuard page only.** The menu keeps the purple FloodGuard shield, now with a Learning, On, Flood or Off label. Its settings show in Advanced; normal mode shows what it learnt.
- Until it has learnt, the hop limits start at 32 for unscoped flood packets and 8 for adverts (MeshCore's own default). They apply while FloodGuard is on.
- **Soak test** (`tests/soakfloodguard.py`, part of the test suite): days of simulated traffic, minute by minute, through FloodGuard and openHop's rule engine: a quiet rural mesh, a busy town mesh with an evening net, padded floods, short-route floods, on-off floods, a flood during the learning days, a long-distance mesh, a small flood on a busy mesh and an advert storm. No direct messages are ever held, genuine traffic held stays well under 1%, and padded floods are cut by 96 to 100%. Floods that start only a hop or two away are the one kind hop limits can't tell apart, and the test shows that too.
- **Upgrading from 6.0:** FloodGuard values set by hand in 6.0 are cleared once, so every repeater starts learning from FloodGuard's own values (Activity says so). Whether FloodGuard is on or off is kept: anyone who turned it on learns for three days, anyone who turned it off keeps it off. Values set after upgrading are kept as usual.

## v6.0: SpamGuard with FloodGuard (FloodGuard 1.0)
### FloodGuard 1.0: floods of any kind, contained by airtime
Some floods aren't channel messages: encrypted packets with a new identity on almost every one, resent with long, padded routes, until a message arrives dozens of times and people give up on the channel. Nothing in them can be blocked by name or text, and their routes can be faked. What a sender can't fake is how busy your repeater's radio is, so FloodGuard measures that from every packet openHop hears and sends.
- **Steps in only during a real flood.** When the radio is busier than the level you set (15% over five minutes by default) for a minute, and most of that is flood traffic, flood packets that have already come further than this mesh's normal routes are not passed on. It learns how far flood packets normally travel from quiet hours.
- **Tightens while it lasts, lifts by itself.** Two hops tighter every two minutes while the radio stays busy, never below a floor you set (8 hops by default), and removed once the radio has been quiet for ten minutes. Each step is noted in Activity.
- **The mesh keeps working.** Direct (routed) messages, replies and acknowledgements are never touched, and channel messages from people SpamGuard knows always get through. FloodGuard never looks at who sent a packet or what it says. Each repeater protects its own airtime, so a flood is held to the area it is swamping.
- **Its own switch and page.** FloodGuard sits under the SpamGuard name in the menu, with its own purple shield and an on/off switch, and has its own page (in normal mode too): what it's doing now, flood packets per hour, how busy the radio was each hour against the level it steps in at, and its settings. While it's containing a flood the Overview says so, the menu shows "Flood", and its limit is listed on the Blocks page with the other blocks.
- **Same graphs, same data.** The Overview graphs can show the flood packets FloodGuard stopped next to the spam, in their own colour: a switch picks Spam (the default), Spam and floods, or Floods.
- **Hop limits like MeshCore's.** Settings has fixed hop limits for unscoped flood packets and for adverts, the same as MeshCore's `flood.max.unscoped` and `flood.max.advert` (openhop_repeater#426). They work with or without flood containment.
- Off until you turn it on, and never switched on by applying a settings profile. In Monitor it only counts what it would have stopped. `tests/testfloodguard.py` checks it against openHop's own rule engine.

### SpamGuard 6.0
- Quieter buttons (such as Keep until I remove it, and the lockdown times) now have a visible edge, so they read as buttons on touch screens too.
- Based on the flood-control proposal from the Dutch MeshCore community (MeshCore #3278). Thank you.

## v5.37
- The Overview's number tiles line up in even rows (three across in normal mode, four in Advanced, two on a phone), and "24 h" no longer splits across lines in the small print either.
- README: requirements (hardware, software, space, memory and CPU, limits) moved into Advanced next to the tested systems, the storage details merged into it, Health lists the warnings it gives, and outdated lines about known people and lockdown corrected. New screenshots, and GitHub issue forms for bug reports and ideas.

## v5.36
Found with a new red-team simulation (`tests/redteam.py`): six hours of ordinary chat, then three hours of fourteen overlapping kinds of spam attack, every message judged by openHop's real rule engine. Before these fixes it stopped 60% of the spam and wrongly held a third of regulars' messages; now it stops about 96% and wrongly holds under 1.5%, across several runs.
- **No more lock-outs on a busy mesh.** Several regulars saying the same everyday thing ("good evening mesh") could look like a campaign to a freshly installed SpamGuard, and that could snowball into a block on a whole route next to your repeater, after which nobody could become known. Now everyday phrases from people who have been chatting for a while don't count as spam, a route that regulars depend on is never blocked for "changing identity", and SpamGuard keeps getting to know regulars even if one of its blocks wrongly catches them.
- **Campaign blocks correct themselves.** A text block that keeps catching several people SpamGuard knows, heard from where they usually are, is stopped and noted in Activity, because that is ordinary chat. Someone copying a regular's name from somewhere else doesn't count.
- **Short automatic lockdown during a big flood.** When lots of made-up names pour in through many different repeaters at once, faster than single-repeater blocks can follow, only people SpamGuard knows get through for 15 minutes, then it stops by itself and says so in Activity. Newcomers are held for those 15 minutes too, so it can be turned off under Advanced, Blocking by source repeater.
- The simulation now runs with the other tests and fails if less than 90% of the spam is stopped or more than 3% of regulars' messages are held.

## v5.35
- **See and edit who SpamGuard knows.** Exceptions (Advanced) now lists the known people: everyone SpamGuard has learnt from genuine messages, most recently heard first, with how many genuine messages they've sent and when they were last heard, plus names still being learnt. A search box finds a name among hundreds. **Trust** keeps a name for good, and **Forget** makes someone count as new again and takes them off the list openHop lets through. The list shows names only, never messages. Suggested by a tester in the Dutch MeshCore community.
- **Catches a newer kind of flood.** Floods now use real-looking first names with a random tag added and very short unreadable messages, and SpamGuard now recognises both, so these floods are spotted from the first few messages. Ordinary names and short genuine messages ("ok", "73", emoji) are unaffected. Thanks to the operator who shared a screenshot of one.
- `tests/testknownlist.py` and `tests/testnamedflood.py` cover these.

## v5.34
- **Settings profiles.** Settings (Advanced) has a new Profiles card. A profile is a saved set of detection settings: the sensitivity and every value you changed. **Save current settings as a profile** stores what's in force now, and **Apply** puts a profile back, first listing every value it will change. The card shows which profile is in use and when settings have changed since.
- **Share with other operators.** **Export** downloads a profile as a small file, and **Import a profile file** adds one to your list without applying it. A profile never holds channels, keys, exceptions, the mode, the evidence log or update settings, and a file that tries to is refused.
- `tests/testprofiles.py` covers profiles.
- The idea came from a sister project that reworked SpamGuard's ideas for another app.

## v5.33
- **Removing a duplicate block no longer switches duplicate checking off for that message.** Before, removing one by hand (or pressing Clear automatic blocks) held that text off for 24 hours, so later copies weren't caught at all. Now the copies seen so far are simply forgiven: the next copy counts as a first copy again, and copies after it are held back as usual. Campaign and repeater blocks you remove are still held off for 24 hours.
- **Low duplicate lengths now work.** With "Only for messages at least this long" and "Characters matched by a duplicate rule" set below the old minimum, short messages still got no duplicate rule. A duplicate rule now goes by those two settings only, and when the words in the middle of a message come out too short it takes the characters as they come.
- **Messages with no name in front.** openHop calls their sender "Unknown"; SpamGuard's rules about such a sender now say the same, so they match, and "Unknown" is never treated as a known person.
- **New licence: GNU AGPL-3.0.** SpamGuard stays free and open source, but anyone who shares a copy or a changed version, or runs a changed version for others over a network, must publish their source under the same licence and keep the copyright notice. Versions up to 5.32 remain under MIT.
- Ideas for the first two fixes came from testers in the Dutch MeshCore community, and from a sister project that reworked SpamGuard's ideas for another app. Thank you.
- `tests/testforgive.py` covers these.

## v5.32
**Spam, not opinions.** SpamGuard stops how spam is sent (floods of made-up names, the same message under many names, one name repeating itself), never what people say, and it can no longer be set up to do otherwise.
- A text you block by hand never stops people SpamGuard knows: in openHop it sits after the rule that lets them through. It only stops names SpamGuard doesn't know yet, such as bots and throwaway names.
- A text block needs at least 12 characters of a message, so a single word or someone's name can't be blocked.
- Blocks that also stop people SpamGuard knows (on message text, or on anything passing through a repeater) last at most a week and can't be kept for ever. Other repeater blocks can still be kept until you remove them.
- A known person's message can't be marked as spam. If a real person copies or repeats something, only the extra copies are held back for a while; their first message always goes out.
- The help page explains this under "Spam, not opinions", and `tests/testfreespeech.py` checks it against openHop's rule engine.

**Easier to find your way around.**
- **Channels** has its own page in the menu, in normal mode too, with the channels SpamGuard reads and the ones openHop knows that it doesn't yet. The Overview points there when only Public is being read.
- **Lockdown** moves to the bottom of the Blocks page as an emergency option; the Blocks badge says when it is on.
- **Settings** are grouped in sections you open one at a time, with a search box, and each section says how many of its settings you changed.
- Advanced Blocks folds the short-lived duplicate blocks into one line you can open, so the real blocks stay in view. openHop rule numbers show in Advanced only.
- "Keep" is now **Keep until I remove it**.
- The Overview shows six number tiles in normal mode (Known people moves to Advanced), and labels no longer split "24 h" across lines.
- **Not spam** and **This is spam** on messages are proper buttons, and "Clear this list" only shows when there's something to clear.

## v5.31
Two more suggestions from the testers in the Dutch MeshCore community.
- **Your own rules first, if you prefer.** A new setting, "Put SpamGuard's rules after your own openHop rules" (Advanced, Timing), keeps your own rules at the top of openHop's policy list and SpamGuard's below them. It is off by default, because a broad 'allow' rule of yours would then also let spam through before SpamGuard's blocks are reached. Your own rules are never changed either way.
- **Copy rule summary.** Blocked right now (Advanced) has a **Copy rule summary** button: SpamGuard's rules in openHop, in order, with their openHop rule numbers, what each does and its name, ready to paste into a message or notes.

## v5.30
More from the testers in the Dutch MeshCore community, thank you again.
- **Pick channels from openHop's own list.** Channels already named in openHop's policy settings now appear under Channels SpamGuard can read as "not read yet", each with an **Add** button, and **Add all shown** adds several at once. Their keys come from openHop, so there's nothing to look up or type, and the keys never reach the page. The channels SpamGuard reads are listed separately above. With lots of channels, the search covers both lists and **Show all** lists everything.
- **Which block dropped that packet?** openHop's packet list marks a policy drop with the rule's number ("Policy blocked packet (rule N)"), not its name. Each block on SpamGuard's page now shows its openHop rule number, so you can match them up. A correction to the v5.29 notes: the readable rule names show in openHop's policy settings and its log, but not yet in the packet list. We've asked openHop to add the rule name to the drop reason, so it would show in the packet feed and the packet history too (openhop-dev/openhop_repeater#528).
- The help page explains both.
- `tests/testohchannels.py` covers the channel offer and the rule numbers.

## v5.29
Most of this release comes from detailed testing and feedback in the Dutch MeshCore community. A big thank you to everyone there who tested, reported and suggested.
- **A spam wave can no longer flood openHop with rules.** The "Most rules at once" limit now covers every rule SpamGuard writes, including repeater blocks and the rules that let known people through, and it can't be set above 500. Too many rules can overload openHop, and a tester running a similar tool saw openHop's database lock up after a wave of identical spam on several channels. Repeater blocks get first claim on the space, and short-lived duplicate rules make way first.
- **"Clear automatic blocks" now sticks.** Cleared blocks used to come straight back a minute later, rebuilt from the same spam SpamGuard had already seen, so it looked as if the button did nothing. They now stay away for 24 hours (a duplicate block for as long as it had left). New spam can still make new blocks, and Exceptions, Not re-blocked, Clear lets them back sooner.
- **Readable rule names in openHop.** openHop's packet list shows the name of the rule that dropped a packet, so SpamGuard's rule names now say what they stop and who made them, for example `(yours) text "..."`, `(duplicate)`, `(campaign)`, `(repeating)` or `(auto) via 4C`. You can see at a glance whether a drop was a block you added or one SpamGuard made itself.
- **Fewer rules in openHop.** A block on a source repeater can now be limited to one channel, as text blocks already could, instead of always covering every channel. The rule that lets known people through is now one rule whatever the number of channels, and a message already stopped by one of your text blocks no longer gets an extra duplicate rule as well.
- **Tidy up the lists.** "Possibly genuine, held" and "Recent messages" each have a **Clear this list** button, and a repeater in Spam sources has a **Remove** button. These only tidy the page. Everything stays in the evidence log, and anything new still shows up.
- **Find a channel quickly.** With more than 15 channels, Channels SpamGuard can read gets a search box. You can also add several hashtag channels at once, for example `#chat #test #amsterdam`.
- Duplicate suppression's two length settings ("Only for messages at least this long" and "Characters matched by a duplicate rule") can now go as low as 5 characters.
- `tests/testclearauto.py` covers the clear, the rule names and the rule ceiling.
## v5.28
- **Switches itself from Monitor to Protect.** A new SpamGuard still starts in Monitor, but if nobody comes back to it, it switches itself to Protect once it has watched for at least a day and seen enough spam (or after three quiet days), and says so in Activity. It holds off if you marked anything it would have blocked as genuine, or if several genuine-looking messages were held. The Overview shows when it will switch, with a **Stay in Monitor** button, and choosing Monitor yourself turns it off.
- **Start again from scratch now starts the page again.** The charts, messages, activity and held list show only what happens after the reset, so old and new don't get mixed up. Nothing recorded is thrown away: the evidence log and history are all kept.
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
