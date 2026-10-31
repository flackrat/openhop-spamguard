# Changelog

SpamGuard and FloodGuard ship together as one openHop plugin with one release number (SpamGuard's), but each has its own history below. FloodGuard's version only goes up when FloodGuard itself changes. Versions 5.2 to 5.7 came before the first public release (v5.8), so they were never published as releases and have no download.

## The big picture

The detail is below, newest first. In short:

| Versions | What changed |
|---|---|
| **5.8 to 5.19** | The first public releases, running as their own service on the Pi. Catches spam campaigns sent under many made-up names, finds the repeater spam comes in through and blocks it there while letting known people through, stops copy-paste floods, adds an emergency lockdown, a map of where spam comes from and an optional evidence log. 5.19 adds Docker. |
| **5.20 to 5.37** | Becomes an **openHop plugin**, installed and updated from openHop's own dashboard, with one press to move an older install across. Stops one name repeating itself, switches itself from Monitor to Protect once it's sure, and adds settings profiles and a list of known people you can edit. |
| **6.0 to 6.5** | Adds **FloodGuard**, which contains floods of any kind by how busy the radio is, learns your mesh's normal traffic first, and from 6.2 has its own version number (from 1.0). Also wardriving privacy, catching old messages being sent again, and a watch for radio interference. |
| **6.6 to 6.7** | Catches slow repeating spread through the day, even when the name changes, and adds clearer reports: who has the most held, airtime saved, where floods come in, and one-tap labels. |
| **6.8 to 6.19** | A **protection level slider** that shows what each level would have held on your own traffic, a plainer page, a **Messages** list that works like a mail quarantine, repeat spammers shown as one sender on the map, updates that won't leave a small Pi without SpamGuard, blocking just the route spam starts on, spotting a route that suddenly carries lots of new names, a flood of requests or group data from one repeater, floods spread over a few repeaters, optional counting and checking of signed messages, counting damaged copies of messages, and defences against the usual ways round a spam filter. |

## v6.22.0

- **Harder to borrow trust.** A trusted repeater's code that made-up names keep wearing loses its free pass on that route for a while.
- **Identity tags.** Messages show whether a sender is signed, a copied name, a known name only, or unknown.
- **Shared codes.** A short code several repeaters share needs more than one sign before everything with it is blocked, and is marked on the page.
- **Fixed:** a config file could set the rule limit above its 500 ceiling.

## v6.21.0

- **Parts list with every release.** Each release now carries a signed software bill of materials (`.sbom.cdx.json`) listing what it is made of.
- **Dependency check on every change.** A pull request that adds a dependency with a serious known vulnerability now fails.
- **`main` is protected.** Changes land through a pull request with the checks passing.
- **[OpenSSF notes](docs/openssf.md)** on where the project stands against the Best Practices criteria.

## v6.20.0

- **Limits vary by repeater.** Some limits shift a little around your protection level, differently on each repeater and each week, so tricks tuned to the published numbers aren't reliable. The page shows the values in use, and your own settings are never changed. Turn it off under Timing.
- **Shorter wording.** The page, settings and Activity say the same in far fewer words; the map's explanation is now a line or two. The README is a short front page, with the full reference in [docs/advanced.md](docs/advanced.md) and a [glossary](docs/glossary.md).
- **Fixed:** a fresh install could read its private id from the wrong place on first start.

## v6.19.0

- **More repeat tricks caught:** copies sent to a different person each time, and no free copy after a hold for names that keep repeating.
- **New defences:** a per-name burst limit, link campaigns across new names, trust lost by repeat offenders, and a copied known name arriving the way the spam does.
- **Signed names:** once you trust someone's key, their name without their signature is treated as a stranger.
- **Known names take time:** a name must also have been heard for a while before it counts as known. It follows the protection level.
- **Labels stay visible** in Messages, with when you set them.
- **Reliability:** a standing warning while openHop needs its rule-check fix, and a backup of saved state.
- **Fixed:** an unreadable link in dark mode.
- **FloodGuard 1.5.0.**

### FloodGuard 1.5.0

- **What it stopped, broken down** by reason on the FloodGuard page, including damaged copies.
- **Protection from day one:** while learning, it stops floods beyond the loosest limits it could ever learn.

## v6.18.0

- **Repeats with a made-up code on the end are now counted.** Someone sending the same reply over and over, with a different random code on each copy (for example `@[Sam]🤡` then `rynx95jx`), got past every repeat limit because no two copies were identical. SpamGuard now counts copies by what is left once the code is taken out, and holds the later ones. The block only covers that name's messages starting with the same words; anything else they say, and other people's messages, are left alone.
- **The same link again and again is counted, whatever is written round it.** One name posting the same picture link inside slightly reworded messages was never counted as repeating. The link itself is now counted, per name, against your repeat limit.
- **Names already held for repeating are treated more strictly.** A name that has had a repeat hold started against it twice in a day is held one copy sooner, and once it is held for a link, its other links to the same site are held too, so a fresh picture address no longer gets a free first copy. It wears off after a day.
- **New tests** cover all three, using made-up names and links.

## v6.17.1

- **Blocks you add yourself now count as spam stopped.** A manual block on a repeater or a route was counted as "possibly genuine held" instead of spam stopped, so it didn't show in the spam stopped figures. It now counts as stopped everywhere: the tiles, the graphs and the Messages list. (Blocks SpamGuard makes itself that could catch real people still count as held.)
- **The spam map includes spam that got through.** Spam openHop passed on despite a block was in the totals but missing from the map. It now shows where it came in.
- **The tiles now match the graphs.** "24 h" is exactly the 24 columns of the hourly graph and "7 days" is exactly the seven days of the daily graph (before, they covered a slightly wider window, so the numbers could differ by a few). The map and the table of where spam enters use the same windows.
- **The headline agrees with the tiles.** The sentence at the top ("N spam messages stopped in the last 24 hours") used a separate count that could differ from the Spam stopped tile. It now uses the same figure.
- **A new audit test** checks that the tiles, graphs, per-channel split and map data all agree, including manual blocks and the edges of the windows.

## v6.17.0

- **Damaged copies are counted.** Radio errors sometimes change a few bytes of a message in flight, and the changed copy is passed on like any other. SpamGuard now counts the channel packets it hears whose check fails, and the FloodGuard page shows how much of the last day's packets and airtime they made up.
- **FloodGuard no longer reads damaged copies as a flood.** They still count towards how busy the radio is, but up to a quarter of the airtime they are left out of the flood share, so a noisy hour is less likely to make FloodGuard hold back innocent people. Anything beyond a quarter counts as flood traffic as before.
- **Optional: don't pass on damaged Public copies.** A new setting, off by default, stops this repeater passing on Public channel packets whose check fails, in Protect mode. Direct packets, other channels and packets this repeater sends itself are never touched. One risk is listed with the setting: a packet carries only a one-byte channel code, so a private channel that this repeater doesn't know and that shares Public's code would look damaged. It needs the openHop rule-check fix and is skipped without it.
- **A note about the radio's coding rate.** When the radio uses coding rate 4/5, the FloodGuard page says it can spot but not repair a damaged byte, and that 4/8 can repair one. It says to match the other repeaters near you before changing it.
- **The note under a message's buttons** now mentions Let it through only for messages that have that button.
- **FloodGuard 1.4.0.**

## v6.16.0

- **Optional: count and check signed messages.** Some apps now sign channel messages with the sender's own key. A new setting, **Count and check signed messages**, is off by default. When it is on, SpamGuard counts the signed messages it hears, checks each signature against the key the sender advertised, and shows the totals on the **Overview**: how many were signed, from how many signers, and how many were correct, did not match, or could not be checked yet because the signer's advert had not been heard. It also shows how much airtime signatures use. Only counts and short key ids are kept, never names or what anyone said.
- **Trust a key, never punish a signature.** Nothing is ever held back because a message is signed, unsigned, or fails the check. When a person SpamGuard already knows has sent several correctly signed messages with one key, the Overview suggests trusting that key as theirs, with **Trust it** and **Not now**. Once you accept, a message correctly signed by that key, under that name, is never treated as spam, which protects them from someone copying their name. If two keys sign as one name, SpamGuard suggests neither. You can take the trust back at any time.
- **FloodGuard 1.3.1.** FloodGuard already counts signatures in its airtime, because it works from each packet's full length. It now also shows how much of the airtime they use.
- Thanks to the people who shared how the signed format is laid out so it could be tested.

## v6.15.0

- **A flood spread over a few repeaters is spotted too.** The 6.14 suggestion needed one repeater to carry most of a flood. When flooded requests, anonymous requests or group data come in through up to four repeaters that together carry nearly all of them, **Blocks** now suggests holding that kind of packet from each, marked as spread over a few repeaters. Ordinary traffic spread thinly over many repeaters is left alone. Nothing changes for channel messages or direct messages.
- **One repeater counts once.** The short and long forms of a repeater's name are counted together, so using both no longer splits a flood in two.
- **FloodGuard is harder to dilute.** Direct (routed) packets still count towards how busy the radio is, but no longer lower the share of flood traffic that decides whether to step in. And when short bursts keep coming back, FloodGuard steps in sooner the next time.
- **FloodGuard is now version 1.3.0.**
- **Tested against other meshes' traffic shapes.** Anonymised shapes of traffic from many regions were replayed through the test harness. Ordinary traffic raised no suggestions.

## v6.14.0

- **A flood of requests or group data from one repeater is spotted.** Not all spam is channel text. Communities describe floods of remote telemetry requests, anonymous requests and group data that SpamGuard could not see because those packets are encrypted. When one first repeater sends most of the flooded requests, anonymous requests or group data your repeater hears within a short time (or, at a lower count, over a couple of hours for a slow steady flood), and a lot of them, **Blocks** now shows a **Suggested block** with **Hold them** and **Not now** buttons. Accepting holds only that kind of flooded packet through that repeater, for a limited time. Channel messages, direct (routed) messages and everything else through the repeater are untouched. SpamGuard looks only at how many arrive, through which repeater and how they travel, never inside a packet.
- **The protection level sets how quick it is.** Gentle waits for the most packets, Tough for the fewest (starred in the settings).
- **Optional: hold it for you.** A new setting, off by default and not changed by the level, applies the hold itself, with the same time limit as route blocks and at most three at once. They are marked as automatic in **Blocks** and can be removed in one tap. In Monitor mode a hold only watches.

## v6.13.0

- **A quick burst of new names now blocks the route, not the whole repeater.** When the only sign against a repeater is brand-new names, and nearly all of them started on the same first two repeaters, SpamGuard now blocks just that route, with the usual time limit and people it knows still let through. Before, it blocked everything through the first repeater, which also held genuine newcomers using that repeater another way. Made-up names and spam campaigns still block the whole repeater, and so do new names spread over several routes. It is listed in **Blocks** as an automatic route block. A new setting, on by default, turns this back to the old behaviour.

## v6.12.0

- **A route that suddenly carries lots of new names is spotted.** A spammer who keeps changing names but always starts on the same first two repeaters is easy to miss, and a route block only helps once someone notices. When many brand-new names, each posting once or twice, start on the same first two repeaters within a short time, **Blocks** now shows a **Suggested block** with a **Block it** button and a **Not now** button. SpamGuard looks only at names, routes and timing, never at what a message says. People SpamGuard knows are never counted and still get through, and nothing is blocked until you press the button.
- **The protection level sets how quick it is.** Gentle waits for the most new names and blocks for the shortest time, Tough waits for the fewest and blocks for the longest. Both are listed under the level's starred settings.
- **Optional: block it for you.** A new setting, off by default and not changed by the level, lets SpamGuard apply the route block itself, for the time above and with at most three at once. They are marked as automatic in **Blocks** and can be removed in one tap. A route whose first repeater you have already blocked or allowed is left alone.
- Thanks again to Caboosey on the openHop Discord server, whose question started this.

## v6.11.0

- **Block a route.** For spam that always starts on the same first repeaters, you can now block just that route, for example `27>B1`, instead of everything through the first repeater. People SpamGuard knows still get through, and other routes through the same repeater are untouched. Type it in **Blocks**, or press **Block route** on a spam message in **Messages**. A route block can be limited to one channel and has the usual time limit. Until openHop can check the order of a route, your repeater holds any message that passes through all of the repeaters you give; SpamGuard's own records check the order exactly. Thanks to Caboosey on the openHop Discord server for the suggestion.

## v6.10.0
### SpamGuard 6.10.0
- **Messages is now one quarantine list.** Every channel message SpamGuard read is in one place, like a mail quarantine, with what SpamGuard did and why in plain words: Stopped, Held (possibly genuine), Spam let through, or Passed on. Filter buttons show how many of each, copies of one message are grouped (with how many names sent them), and there is a search box and a choice of the last 24 hours or 7 days. Choose a message to see why, how many copies there were, which way it came in and what SpamGuard knows about the sender, and to let it through, stop copies like it, or label it. Tick several to act on them together. It reads the evidence log when that is on; otherwise it shows the last few hours. The old live feed is still there underneath.
- **The Overview's numbers are links.** Spam stopped, Likely spam let through, Spam share and Possibly genuine held each open the message list already filtered to those messages.
- **A repeat spammer is shown as one sender on the map.** Someone whose repeated messages are being held, under one name or several, is drawn as a single purple area placed from the repeaters that hear them first, with lines to each of those repeaters, rather than as several unrelated dots. Every message they send counts towards where they are, not only the copies held, so a spammer whose messages mostly get through still shows up. Nothing is blocked because of it.
- **Size the map by senders as well as messages,** so one busy spammer doesn't outweigh many one-off ones. Senders are counted by a short code, never by name.
- **A map key that is always shown,** for sure placements, best guesses, blocked repeaters, repeat spammers and your own repeater, plus how many couldn't be placed.
- **Show these messages** from any point on the map, or from the table of spam sources, opens the message list filtered to the spam that entered there, or to everything from that sender.
- **Copies of a message one name kept repeating that went out before the limit** now count as spam let through in the message list, instead of passing as normal.

## v6.9.1
### SpamGuard 6.9.1
- **Updates no longer leave a small Pi without SpamGuard when a library has just had a new release.** When one of SpamGuard's libraries puts out a new version, it often comes as source code first, with ready-made builds for Raspberry Pis following a day or so later. openHop would then compile it while installing, which on a Pi 3 can take longer than openHop waits, so the install stopped partway and nothing was running. SpamGuard's check before updating now asks for exactly what openHop's install would fetch, and if anything would have to be compiled it stops the update before anything is changed, says which library, and suggests trying again tomorrow (or Update anyway).

## v6.9.0
### SpamGuard 6.9.0
Improvements to the protection level from user testing, from first-time users to experts.
- **No more dead end on a new install.** "What this level would have done" now has a Turn on the evidence log button right there, instead of pointing to a Settings page that only shows in Advanced. "See it in Settings" next to your own values switches Advanced on and takes you to that setting.
- **An honest suggestion.** Until you have marked at least five held messages as spam or fine, the pin on the slider says "Early guess", is worked out from repeats alone and never goes past Firm.
- **Your marks show straight away.** Spam and Fine stay pressed on the messages worth a look, and the count of messages you have marked goes up at once, not after the next daily run.
- **What this level does now says what really applies,** including values you set yourself, marked as yours. "Use the suggested level" asks about your own values, as moving the slider does.
- **The slider comes first on a phone,** straight after the spam numbers and before Mode.
- **For experts:** the Settings page shows the protection level as a number you can type, there is a switch to turn the daily replay off (Settings, Evidence log), and durations read naturally, such as "about a day and a half".
- **Private channels are left out of the replay, and the page says how many,** since their keys never leave SpamGuard. Only the Public channel and hashtag channels are replayed.
- **Show the numbers** under the chart of what each level would have held, like every other chart.
- **One word for it.** The protection level panel now says "held" throughout.

## v6.8.0
### SpamGuard 6.8.0
- **A protection level slider instead of Relaxed, Balanced and Strict.** The Overview has a slider from Gentle to Tough that warms from teal to red as it gets tougher, and every point in between works. 0, 50 and 100 are exactly the old Relaxed, Balanced and Strict, so nothing changes until you move it. Under the slider it says in plain words what that level does: how many copies are let through, for how long further copies are held, and how long automatic blocks last.
- **See what each level would have held on your own traffic.** Once a day, at the lowest priority so the radio always comes first, SpamGuard replays the last two days of the evidence log at eleven points along the scale. Open "What this level would have done" to see how many messages that level would have held, how many were one name repeating itself, and how many are worth a look, with a small chart across the whole scale. Messages worth a look have Spam and Fine buttons; the more you mark, the better the Suggested point on the slider. Nothing is changed by the replay itself. It needs the evidence log turned on.
- **Tougher also means for longer.** The level now also sets how long a quick-repeat block lasts (30 minutes, 1 hour or 2 hours across the scale), how far back the all-day repeat count looks (12, 24 or 36 hours) and how long automatic blocks last (3, 6 or 12 hours). Balanced is the same as before.
- **Values you set yourself are kept.** If you have changed one of the values the level sets, the slider says so, and moving it asks whether to use the level's values or keep yours.
- **Plainer words throughout.** Settings and help no longer talk about hashes, de-duplication, unscoped packets or detection windows; for example "Duplicate suppression" is now "Copies and repeats".
- **Older choices still work.** A config file, Docker setting or saved profile with relaxed, balanced or strict is read as 0, 50 or 100. The new config setting is `level` (`SPAMGUARD_LEVEL` for Docker).
- **The replay tool is about nine times quicker,** and can replay protection levels: `replay.py LOG --levels 0,50,80,100`.

## v6.7.0 (FloodGuard 1.2.5)
### FloodGuard 1.2.5
- **Where floods come into the mesh.** The FloodGuard page now lists the first repeaters on the routes of the flood packets it stopped, so you know which repeater owner to talk to.
### SpamGuard 6.7.0
- **Most held, last 7 days.** A new table on the Blocks page lists the names with the most copies held back, how many messages a day they send, and how many were held today. When a name took over another name's repeat count, the two are shown together, so one sender behind several names reads as one. Only counts are shown, never what anyone said.
- **Name changes are shown.** When a name carries on another name's repeat count, Activity and the block both say which name it carried on from.
- **Airtime, last 7 days.** A new chart on the Overview shows the minutes a day the radio spent on traffic, next to the airtime saved by stopping spam and by FloodGuard.
- **One-tap labels.** Each recent message has Spam and Fine buttons that only record your opinion: nothing is blocked or trusted. Labels go in the evidence log, so a replay can show how often SpamGuard got it right.
- **Easier on a phone.** The Overview now opens with the spam numbers. Mode and Sensitivity follow, without their explanations, then the graphs, with less text throughout.
- **"Most channel messages are on channels SpamGuard can't read" can be dismissed.** It stays hidden on that device for 30 days.
- **How busy the radio was, as a line.** The Overview shows the busiest five minutes of each hour as a line next to the other graphs, with FloodGuard's step-in level dashed. The FloodGuard page uses the same line, and hours with no measurement show as a gap.
- **All examples are made up.** The examples in the code comments, tests and documentation are now all invented, with no real names, messages or places.

## v6.6.2
### SpamGuard 6.6.2
- **Changing name no longer restarts the all-day repeat count.** When a new name takes over sending the same long message after another name has stopped, it carries on that name's count, so its copies are held straight away. Two people posting the same thing at the same sort of time are still counted separately, and a tiny change to the text no longer counts as a new message.
- **"Spam let through" no longer counts regulars.** A name SpamGuard knows from genuine messages was counted as spam let through if its name happened to look made-up, so a regular's test messages could make the stop rate look much worse than it was. Known names are no longer counted, and the tile is now called "Likely spam let through".

## v6.6.1
### SpamGuard 6.6.1
- **See what each rule says.** The "N rules in openHop" line at the foot of the page is now a button. It opens a list of SpamGuard's rules in the order openHop checks them, each in plain English (for example "Blocks a packet that is a channel message, contains the text ..."), with a Copy as text button. Channel keys are never shown.
- **Sensitivity now sets the repeat limits too.** Relaxed, Balanced and Strict now also set how many copies of a message are allowed before the repeat guard acts (4, 3 or 2), the same limit for the all-day repeat guard, and how long its hold lasts (2, 3 or 6 hours). Balanced behaves exactly as before.

## v6.6.0
### SpamGuard 6.6.0
- **Slow repeating is now caught.** The repeat guard only notices copies sent within minutes of each other, so a name posting the same long message once an hour, all evening, slipped past it. SpamGuard now also counts how many times one name sends the same long message in a day. After three, further copies are held for three hours, and while they keep going one copy gets through each time the hold ends. The first copies and anything new from that name still go out, and it only ever counts repeats, never what a message says. Copies of one send that arrive by several routes count once. It is on by default, and the limit, the time window and the hold are in Advanced under Duplicate suppression. Ordinary repeats, such as re-posting a notice a few times a day, are left alone.

## v6.5.6 (FloodGuard 1.2.4)
### FloodGuard 1.2.4
- **A flood no longer teaches FloodGuard that flooding is normal.** On a busy site FloodGuard raises its busy limit to fit the traffic, but it counted the hours it had itself flagged as floods, so a long flood could push the limit up and make the next one harder to spot. Flagged hours are now left out, and if most of the hours it heard were floods it learns nothing from them. The busy limit also stops at 30%, however busy the site is.
### SpamGuard 6.5.6
- **No more false "bad" health when openHop does not run as a service on this computer.** systemd reports "inactive" for a service it has never heard of, so a plugin install with openHop in Docker or elsewhere could show the openHop service as stopped. SpamGuard now believes systemd only when the openHop service is really installed here. Found by the new automatic checks on GitHub.

## v6.5.5 (FloodGuard 1.2.3)
### FloodGuard 1.2.3
- **FloodGuard no longer holds back genuine long-route traffic on a busy mesh.** On a busy mesh many genuine messages arrive over long routes, so FloodGuard's made-up start of 16 hops, tightened to a floor of 8, held back messages from senders SpamGuard didn't know yet. The cause was the same trap as the busy limit: it learnt how far flood packets normally come only from quiet hours, and a busy radio never has any. Now:
  1. Hop counts are also kept for every hour (two days, small), and when there are too few quiet hours the normal route length, and the always-on unscoped and advert hop limits, are learnt from those instead.
  2. FloodGuard holds nothing back until it knows how far flood packets normally come (about 200 in a day), unless you set the lowest hop limit yourself. Until then it counts and says so. The made-up default no longer decides anything.
  3. The Activity note when learning ends called every limit "(yours)", even recommended ones. It now says yours, recommended, or nothing for learnt values.
### SpamGuard 6.5.5
- **The plugin no longer compiles PyYAML on a Raspberry Pi.** The real cause of the update that left SpamGuard uninstalled: the plugin asked for `pyyaml`, but the ready-made Raspberry Pi build is published as `PyYAML`, and pip 23.0 (Raspberry Pi OS Bookworm) throws it away over the capital letters and compiles it from source instead. On a Pi 3 that can outlast openHop's wait. The plugin now asks for `PyYAML`, so the ready-made build is used and the install takes seconds. Checked with the same pip version against a copy of the mirror's naming.
- **An update that can't install stops before it removes anything.** Before openHop replaces the running version, SpamGuard checks that the new version's libraries are available as ready-made builds on this machine. Only a clear "none exist" stops it (no network, no pip or any other doubt lets the update go ahead), and the Updates box then explains, with an **Update anyway** button. The README says how to get SpamGuard back from the Plugins page if an install is ever cut short. It can be turned off with `plugin_preflight: false` in the config.
- **Fewer writes to the SD card.** SpamGuard refreshes its "I'm in charge of this repeater" marker in openHop every 10 minutes instead of every 5. That marker is rewritten into openHop's policy file each time, which was the most regular write SpamGuard made. The marker still has five minutes of slack before another copy would treat it as stale.
- `tests/testpreflight.py` (new) covers the check and the update flow; `testplugin.py`, `testmigrate.py` and `testupdprog.py` cover the PyYAML spelling, the ten-minute refresh and the new button.

## v6.5.4 (FloodGuard 1.2.2, unchanged)
### SpamGuard 6.5.4
- **Shorter FloodGuard notices.** The two FloodGuard boxes took most of a phone screen; each is now two or three lines. The longer advice for a flood that has run for a day sits under the box instead of inside it.
- **Interference now shows on the Overview.** When the radio channel's noise stays well above this site's normal, a short notice says by how much and how far the repeater now hears, with a link to the FloodGuard page. Before, it was only on the FloodGuard and Health pages and as a small badge in the menu.

## v6.5.3 (FloodGuard 1.2.2)
### FloodGuard 1.2.2
- **A repeater in a busy place can now learn its own busy limit.** FloodGuard used to set its busy limit only from hours when the radio was *below* the starting limit (15%), and needed two days of them. On a repeater that normally sits above 15% there were none, so it stayed on the starting limit and was "containing a flood" for days at a time. It now falls back to every hour and takes twice the middle one (a flood of a few hours can't move a middle value), still inside its 10 to 40% range, and says so in Activity. Repeaters with quiet hours learn exactly as before. Then, as always, it moves a little each day.
### SpamGuard 6.5.3
- **FloodGuard is shown calmly once it has been on for an hour.** A flood that has just started is still amber. After an hour it becomes a quiet notice ("holding back long-distance flood packets") on the Overview and the FloodGuard page, with the radio's busy level against its limit. After a day the page adds that this usually means the site is simply busy, and points to the busy limit under Settings. The Details link in these notices is also darker, so it meets the contrast guidelines in the light theme.
- `tests/testfgcalm.py` checks the wording, colours and accessibility; `tests/testfloodguard.py` covers the busy-repeater learning.

## v6.5.2 (FloodGuard 1.2.1, unchanged)
### SpamGuard 6.5.2
- **The Update box shows how far the update has got.** While an update installs, the banner and the Updates box show a percentage bar and the last two lines the installer printed, so a slow Pi can be told apart from a stuck one. As an openHop plugin, the lines come from openHop's own install feed; on a normal install, from the updater's install log. The percentage is a guide, not a measurement: the download counts truly, but the installer doesn't say how many steps it has, so that part moves along with its output and never goes backwards. A failed update shows the reason, with no bar.
- The page is checked for accessibility (the bar is announced as a progress bar), and text from the installer is only ever shown as text. `tests/testupdprog.py`, `tests/testupdsh.py` (runs `update.sh` for real against a made-up release) and an extended `tests/testpluginops.py` cover it.

## v6.5.1 (FloodGuard 1.2.1, unchanged)
### SpamGuard 6.5.1
- **Fewer false alarms from capital-letter names.** A sender name written in capital letters only, with no digits, such as a node or club abbreviation, was being scored as made-up, so ordinary conversation from that name showed up as spam let through on the charts. Such names now count a little, not as made-up. Names with digits or mixed case, and any pattern you add yourself, are scored as before. `tests/testnames.py` covers it.
- **Clearer chart legend.** The orange bars now read "Looked like spam but not blocked (no block in place yet, or Monitor mode)", which is what they count.
- The release notes of v6.0, v6.1, v6.3, v6.4, v6.4.1, v6.4.2, v6.4.3 and v6.5.0 on GitHub were one-line stubs because the notes were looked up by an exact heading. They now show these full notes, and a stale duplicate v6.2 section was removed.

## v6.5.0 (FloodGuard 1.2.1, unchanged)
### SpamGuard 6.5.0
- **Route blocks on a mesh that mixes hop sizes.** Each sender picks its own hop size, so a mesh can carry 1-byte and 2-byte hops at once (roughly half of UK repeaters now send 2-byte hops). Route blocks used to be written only at the size of the newest packet, so they missed traffic at the other size and were rewritten whenever the size flipped. They are now written at every size seen in the last day.
- **Shared-ID check.** A 1-byte hop can belong to more than one repeater. SpamGuard now remembers the repeaters it hears in adverts, and a block learnt from a 2-byte hop is only shortened to 1 byte when no other repeater heard here shares that byte. Otherwise the short form is left out, so the block can't stop that other repeater's traffic, and it still applies to the 2-byte hops it was learnt from. A 1-byte block on a byte that more than one known repeater uses is kept, as it is the only form there is, and Health says so. This only ever makes blocks match fewer repeaters, never more. Works offline: it only uses adverts this repeater hears.
- Health explains blocks left out for either reason. Rules are rebuilt when the hop sizes in use or the known repeaters change, and openHop's policy is only written when the rules differ.
- `tests/testsharedid.py` checks all of this with openHop's own policy engine.
- **Confidence on the spam map.** Each pin now says whether any other repeater heard here uses the same route code, and how many of those have no location. A pin with a shared code gets a dotted outer ring, and its popup says the spam may have come through one of the others instead. A pin with a unique code says so. Screen readers hear the same. Like the rest of the map, this only uses repeaters this one has heard. `tests/testmappins.py` checks it in a browser.

## v6.4.3 (FloodGuard 1.2.1, unchanged)
### SpamGuard 6.4.3
- **Power warning.** Health now reads the Pi's power status with `vcgencmd get_throttled`. If the supply is dropping below its safe voltage right now, Health says so. If it has dipped since boot, Health says that instead. Low power is a common cause of a radio that drops out, which looks like missed sends. On a machine without `vcgencmd` nothing is shown.
- **Intermittent transmit failures.** The radio warning only fired when every recent send failed. Health now also warns when a real share of transmits failed in the last 15 minutes, even if some got out, for example 3 failed out of 10. A few failures among many sends are not reported.
- `tests/testradio.py` covers both warnings and the power readings.
- **Wardriving on a shared channel code.** On a wardriving channel that shares its one-byte code with another channel, SpamGuard now holds back pings in both forms: `@[MapperBot]...` and `MM:...`. Before, the `MM:` form got through on those channels. `tests/testwardrive.py` covers both.
- **Wardriving is one switch.** The wardriving channel is fixed to #wardriving, the one MeshMapper uses, so the channel list setting is gone. A channel listed in an older version is no longer covered.

## v6.4.2 (FloodGuard 1.2.1, unchanged)
### SpamGuard 6.4.2
- **Route blocks follow openHop's hop size.** openHop can send each hop as 1, 2 or 3 bytes (its `path.hash.mode`). Route blocks used to be matched against the size they were learnt at, so changing the mode quietly stopped them. They are now written at the size openHop sends now: a 2-byte hop learnt earlier counts as its 1-byte form when 1-byte hops are in use. A 1-byte block can't match 2-byte hops, so it stays off until that route is seen again, and Health says so. Allow exceptions for known origins follow the same rule.
- **Settings wording.** The "Your own openHop rules first" setting now says exactly which blocks sit after your own rules (route blocks, links, lockdown and blocks set to let known people through). Those are written after your rules so that a known person's exemption can't skip your own drop rules; that is unchanged.
- **Hop limits.** FloodGuard's hop-limit help now says openHop's own Max flood hops setting also applies, and that the lower limit is the one that counts.
- Limit: if one mesh mixes hop sizes at once, only the most recent size is written. `tests/testhashsize.py` checks the rules with openHop's own policy engine.

## v6.4.1 (FloodGuard 1.2.1)
### SpamGuard 6.4.1
- **Standing rules always stay in openHop, inside the rule limit.** The wardriving rule was already never dropped, but it was added on top of the limit ("Most rules at once"), so a heavy spam wave could take SpamGuard one or two rules over it. It now counts towards the limit, and the blocks share what's left.
- **Health says when the radio stops transmitting.** If openHop's sends keep failing (three or more in 15 minutes with none getting out), Health shows a problem: messages from your own companion aren't leaving the repeater and nothing is being repeated. The usual cause is a USB radio board dropping off the Pi, often from a weak power supply. It clears as soon as a send gets out again. `tests/testradio.py` covers it.
### FloodGuard 1.2.1
- FloodGuard's rules (the flood limit and the hop limits) and the known-people rule they rely on can no longer be pushed out by a heavy wave of other blocks, such as a spammer changing repeater identity many times. The newest other blocks are left out instead, as before.
- `tests/testrulecap.py` checks the limit with a wave of 50 blocks.

## v6.4 (FloodGuard 1.2)
### FloodGuard 1.2: interference on the channel
- **Interference watch.** openHop measures the noise on the radio channel every 30 seconds; FloodGuard now reads those measurements (and the last week of them at start), learns what's normal for this site over about six hours, and reports when the noise stays 10 dB or more above normal for five minutes. That's what a nearby transmitter that never stops looks like (faulty or non-compliant equipment with an always-on carrier), or jamming.
- **Says what it means.** The FloodGuard page, Health and Activity say how far above normal the noise is and roughly how much of its normal hearing range the repeater still has (each 6 dB roughly halves it). The menu shows "Noise" next to FloodGuard while it lasts.
- **Records the evidence.** Each episode is kept with its start, length, peak level and how many packets were still heard, and **Copy the record** gives a plain summary with times in UTC and the frequency, to send to whoever looks after the equipment or to a radio regulator.
- Short bursts (someone transmitting nearby for a minute or two), small drifts of a few dB, and floods (which raise the measured noise with traffic the radio can still decode) aren't reported. Hours with interference don't change what counts as normal.
- On by default; the level is in FloodGuard's settings (Advanced). `tests/testinterference.py` covers it with a simulated always-on carrier.

- **While FloodGuard is learning, a flood is shown as counted, not contained.** The FloodGuard page, the Overview, the Blocks page, the menu and Activity used to say "containing a flood" during the learning days even though nothing was held back; they now say it is only counting, and why.
- **Start again from scratch now resets FloodGuard too:** it forgets what it learnt and learns this repeater's traffic again for three days. Recorded interference is kept.
- Kinder to SD cards: FloodGuard's record of normal routes is folded into one entry per day after the first day (about a fifth of the size, same learnt values), hourly airtime totals are kept in whole milliseconds, and a flood limit tightening a step no longer forces an immediate save (starting and lifting still do).

### SpamGuard 6.4
- The Help page showed the wardriving section twice; now once.
- **Settings reset** explains that FloodGuard's settings are reset too, and that what FloodGuard has learnt is kept (Reset and learn again on the FloodGuard page relearns).
- Kinder to SD cards: the state file is written compactly, about a sixth smaller, so each save writes less.

## v6.3 (FloodGuard 1.1, unchanged)
### SpamGuard 6.3
- **Replay guard: old messages sent again.** Some devices pick up channel messages and send them out again later, with their own clock (sometimes wrong by months or years) and sometimes with the sender's name cut short, so one message arrives many times over. When a message turns up again that was first heard at least half a minute earlier, under the same name with a badly wrong clock or under a cut-short copy of the name, further copies of it from that name are held back for six hours. The original always went out first, the same text from anyone else is untouched, and anything new from that name still goes out.
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
- **A spam wave can no longer flood openHop with rules.** The "Most rules at once" limit now covers every rule SpamGuard writes, including repeater blocks and the rules that let known people through, and it can't be set above 500. Too many rules can overload openHop, and a big wave of identical spam across several channels can bring openHop's database to a standstill. Repeater blocks get first claim on the space, and short-lived duplicate rules make way first.
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
- **Fewer genuine people mistaken for spammers, especially outside the UK.** Some name styles that are common on meshes in other countries were being counted as made-up, which on a busy repeater could add up to a block. Checked against a large set of real names from meshes in several regions, this cuts those false alarms substantially, with no change to the spam caught.
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
- Repeater blocks now end sooner after the spam through that repeater stops (new setting: Advanced > Timing > Repeater blocks last for). The same spam stays blocked, with fewer genuine people held. Text blocks keep their times.
- New Possibly genuine, held panel on the main page: messages held in the last 24 hours by a repeater, link or lockdown block from names that don't look made-up, each with a Let through button that trusts the name. It only appears when there's something in it.
## v5.10.2
- Removed blocking a sender by name (added in 5.10). A repeater is shared, so a block on a person silences them for everyone downstream, invisibly, and is easy to forget. Names can also be copied, so it can hit the wrong person. SpamGuard now sticks to spam behaviour; muting a person belongs in each user's own MeshCore app. Any sender blocks already set are removed on update, with a note on the page.
- README: new section "What SpamGuard blocks, and what it doesn't".
- Includes v5.10.1: far fewer SD card writes (about 33 MB a day instead of 170 MB), and a limit on how large the known-names list can grow.
## v5.10.1
- Kinder to SD cards: SpamGuard's working file is now saved straight away only for important changes (a real block, a newly known person, anything you do on the page), otherwise at most every 5 minutes. On a typical day that is far fewer writes, around 33 MB a day instead of about 170 MB. A clean restart or update still saves everything; a power cut loses at most 5 minutes of learning.
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
