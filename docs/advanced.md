# Advanced

Click a heading to expand it.

<details>
<summary><b>The web page</b></summary>

- **Menu**: a side menu like openHop's own (a slide-out menu on phones), with SpamGuard's and FloodGuard's versions at the top and FloodGuard's state (Learning, On, Flood, Off) next to its name. **Overview**, **Protection** (blocks with the emergency Lockdown, possibly genuine, channels with the wardriving option, FloodGuard), **Monitoring** (messages, spam sources) and **System** (health, updates, help).
- **FloodGuard page**: what it's doing now and what it has learnt, flood packets per hour, how busy the radio was, interference on the channel with recorded episodes, its off switch, and (in Advanced) its settings. Advanced adds campaigns, activity, settings (in collapsible groups with a search box), exceptions and the evidence log.
- **Overview**: mode, the protection level slider (with what each level would have held on your own traffic), and the numbers at a glance: spam stopped, let through, spam's share of channel traffic, airtime saved, genuine messages held, known people. Charts show the last 24 hours, the last 7 days, and which hours of the day spam usually arrives, with a switch to show FloodGuard's flood packets alongside.
- **Messages**: every channel message in one quarantine list, filtered by what SpamGuard did (stopped, held for review, spam let through, passed on), with copies grouped, a search box, the reason for each, and Let through, Stop copies like this and label buttons. The Overview's numbers open it already filtered.
- **Spam sources**: where spam enters the mesh, on a map and in a table with Block / Never block buttons. A repeat spammer heard through several repeaters is shown as one sender, and circles can be sized by messages or senders. SpamGuard works out where each spam message most likely entered the mesh, learning from repeater adverts as it goes, so short repeater codes shared around the country don't scatter the map; it can optionally use the public MeshCore map to place far-away repeaters. By default the map only shows entry points it is sure of; tick "Show best guesses too" to add the rough ones. The map needs internet access on the device viewing the page; the table works without it.
- **Long lists** (messages, blocks, activity) show 10 at a time with **Show more**.
- **Advanced** (switch at the bottom of the menu): every setting with what it does and a "Watch out" note on its side-effects, per-block controls, per-repeater statistics, spam campaigns, exceptions (trusted senders, the known people list with Trust and Forget, repeaters and texts never blocked), settings profiles, the evidence log and an activity log. Channels have their own page in the menu.

</details>

<details>
<summary><b>Known people, links and Lockdown</b></summary>

SpamGuard keeps a list of names it has seen sending genuine messages. The list goes into openHop as a policy object, `@spamguard.known_senders`, with one "let known people through" rule, placed after your own rules. The blocks below that rule never stop a known name:

- **Repeater blocks** block *anything passing through* the spam repeater, except known people, and end a while after the spam through it stops (Advanced > Timing). People held this way who don't look like spammers are listed under **Possibly genuine, held** on the main page, with a **Let through** button. The older "Routes starting there" and "Anything passing through" choices are still in Advanced.
- **Route blocks you add yourself** hold messages whose first repeaters are the ones you give, in that order (for example `27>B1`), for spam that always starts the same way. They are much narrower than blocking the first repeater, and known people still get through. Add one in Blocks, or with **Block route** on a spam message in Messages. Until openHop can check the order of a route, your repeater holds any message that passes through all of them.
- **Suggested route blocks.** When many brand-new names suddenly start on the same first two repeaters, Blocks suggests blocking that route, with **Block it** and **Not now**. It looks at names, routes and timing only, never at what a message says, and nothing happens until you press the button. How quick it is follows the protection level. An optional setting, off by default, lets SpamGuard apply it for you, for a limited time and at most three at once.
- **Narrower automatic blocks.** When the only sign against a repeater is brand-new names and nearly all of them started on one route, SpamGuard blocks just that route rather than everything through the repeater. Made-up names and spam campaigns still block the whole repeater.
- **Floods that aren't channel text.** When one first repeater (or up to four together) sends most of the flooded requests, anonymous requests or group data your repeater hears, Blocks suggests holding that kind of packet from that repeater for a while, with **Hold them** and **Not now**. These packets are encrypted, so only counts, routes and timing are used; channel and direct messages are never held by this. How quick it is follows the protection level. An optional setting, off by default, applies it for you, at most three at once.
- **Signed messages (optional).** When turned on in Settings, SpamGuard counts signed channel messages, checks each signature against the sender's advertised key, and shows the totals and the airtime they use on the Overview. It can suggest trusting a known person's key, so a copy of their name can't borrow their trust: once you accept, a message under their name without their signature is treated as a stranger, and held from repeaters they never use. Otherwise it never holds anything back for being signed or unsigned, and keeps only counts and short key ids.
- **Links from names it doesn't know** are held while a spam campaign is under way. Advanced > Known people can make this always or never.
- **Text blocks you add yourself** only ever stop names SpamGuard doesn't know yet.
- **Lockdown** (at the bottom of the Blocks page): for 30 minutes to 2 hours, only known names get through on the channels SpamGuard reads. New people are held too, so it's for heavy attacks only. The lockdown ends by itself. During a big flood from many repeaters at once SpamGuard starts a 15-minute lockdown itself (Advanced > Blocking by source repeater can turn that off).

Things to know:

- How quickly a name becomes known is adjustable (Advanced > Known people), and Advanced > Exceptions lists everyone it knows, with **Trust** and **Forget**. Automatic campaign blocks apply to everyone, because spammers copy known names, but one that keeps catching regulars heard from their usual repeater removes itself.
- Names are forgotten after a long silence. The list is in openHop's `policy.yaml`; channel names are public anyway, but bear it in mind if you share that file.

</details>

<details>
<summary><b>Health and self-repair</b></summary>

The **Health** panel on the page shows whether SpamGuard is working: how long it has been running, when it last checked, whether openHop is answering, whether all its rules are in place in openHop, and how many times it has restarted. Advanced adds the Pi's temperature, memory, disk and load.

SpamGuard looks after itself:
- **Restarts if it hangs or crashes.** As a plugin (or in Docker) it watches its own checking loop and quits if it ever gets stuck, and openHop (or Docker) starts it again. The older install checks in with systemd after every pass instead, and systemd restarts it if it stops checking in for 90 seconds.
- **Puts its rules back.** Once a minute it confirms openHop still has exactly its rules (after an openHop restart, restore or manual edit), and restores them if not. Your own rules are never touched.
- **Keeps protecting while down.** The rules live in openHop, so blocking carries on even if SpamGuard is stopped. Blocks just don't expire or update until it's back.
- **Measures openHop's delay.** The page shows how far behind real time openHop's packet list is and warns when it is 30 seconds or more behind, because spam copies arriving in that gap get through before a block starts. Each evidence-log line also records how late SpamGuard saw the message.
- **Notices a deaf radio.** If openHop reports no new packets of any kind for 20 minutes, the Health panel warns that its radio may have stopped receiving.
- **Asks openHop for as little as possible.** SpamGuard reads only packets newer than the last ones it saw, using a query openHop's database answers from its time index (older openHop versions fall back to the recent packet list).
- **Warns early.** Health warns when the disk has under 200 MB free, memory is under 10% free, the Pi reaches 70 °C (a problem at 80 °C), a check takes longer than the gap between checks, talking to openHop fails 20 or more times in an hour, or openHop's repeater service isn't running.

As a plugin, openHop's **System > Plugins** page shows whether SpamGuard is running, with a **Logs** button. On the older install, quick checks from the command line:
```
systemctl is-active openhop-spamguard          # "active" = running
curl -s http://127.0.0.1:8091/health           # "state": "ok" / "warn" / "bad"
systemctl show openhop-spamguard -p NRestarts  # how many times systemd has restarted it
```
`/health` returns HTTP 200 when healthy and 503 when something is wrong, so it can be watched by a monitoring tool such as Uptime Kuma.

</details>

<details>
<summary><b>openHop running behind</b></summary>

Most repeaters never see this. If the Health panel shows **openHop delay** in minutes rather than seconds, openHop is struggling to save the packets it hears (usually an older Pi with a large packet history), so SpamGuard sees spam late. Health then suggests a fix to run. Keeping 7 days of packet history instead of 31 also helps: see [docs/openhop-fresh-install.md](openhop-fresh-install.md).

</details>

<details>
<summary><b>Blocked spam still getting through (openHop rule-check fix)</b></summary>

openHop's rule checker has a bug that can mix up one channel message with an earlier one, so spam a rule should stop is sometimes passed on, or a genuine message dropped.

SpamGuard has a one-line fix for it, which keeps a copy of openHop's original file. On the older install it applies the fix automatically and puts it back if an openHop update removes it (turn that off under Advanced > Settings > Updates). A plugin can't change openHop's own files, so as a plugin the Health page tells you when the fix is missing and gives the one command to run on the Pi. If openHop itself runs in Docker the fix can't be applied, and openHop's own fix is the cure. `sudo bash tune-openhop.sh --undo` removes it. The bug has been reported to openHop ([#520](https://github.com/openhop-dev/openhop_repeater/issues/520)); once their own fix is released, SpamGuard sees it isn't needed and the Health page recommends updating openHop instead.

SpamGuard also reads openHop's own record of what happened to each message, so any spam openHop passes on despite a block is counted as let through, and the Overview says so.

</details>

<details>
<summary><b>Updating</b></summary>

SpamGuard looks for a new release once a day (you can turn that off in Advanced > Updates) and shows it in the **Updates** section of its page, with what's new. Nothing is installed until you press **Update**, and your settings, blocks and learnt routes are kept.

As a plugin, **Update** fetches the new plugin file, hands it to openHop and openHop restarts SpamGuard on it. In Docker, run `docker compose pull && docker compose up -d`. On the older install, if the new version doesn't start, the previous one is put back automatically; from the command line:

```
sudo bash /opt/openhop_spamguard/update.sh --check          # installed and latest versions
sudo bash /opt/openhop_spamguard/update.sh                  # install the latest release
sudo bash /opt/openhop_spamguard/update.sh --version v5.9   # install a particular release (also to go back)
```

Or, from your clone: `git pull && sudo bash install.sh`.

**If a plugin update stops, or SpamGuard disappears from openHop's Plugins page.** Before it changes anything, the Update button checks that the new version's libraries (PyYAML and pycryptodome) can be installed from ready-made builds on your machine. If they can't, it stops and says so, with nothing removed, and offers **Update anyway**. The check matters on a Raspberry Pi 3 (or any small Pi), because openHop would otherwise compile the library from source, which can take longer than openHop waits. If that is cut short, the old version is already gone and SpamGuard stays uninstalled until you add it again. To get it back, download `openhop_spamguard-<version>-py3-none-any.whl` from the [latest release](https://github.com/flackrat/openhop-spamguard/releases/latest) and upload it on openHop's **Plugins** page. Your settings and everything learnt are kept in the plugin's data folder and come back with it. From 6.5.5 the plugin asks for PyYAML the way its published files spell it, which avoids the compile on Raspberry Pi OS Bookworm (pip 23.0 otherwise rejects the ready-made build over the capital letters).

How the button works: SpamGuard runs as an ordinary user, so it can't install software. Pressing Update leaves a request file that a small root-owned systemd service (`openhop-spamguard-update`) carries out. It only ever downloads tagged releases of this repository over HTTPS. Changes are listed in [CHANGELOG.md](../CHANGELOG.md).

</details>

<details>
<summary><b>Uninstalling</b></summary>

**Plugin:** on SpamGuard's page press **Pause** and wait a minute (that takes its rules back out of openHop), then uninstall it in openHop under System > Plugins. The plugin's data folder goes with it unless you keep it.

**Older install:**

```
sudo bash /opt/openhop_spamguard/uninstall.sh
```

The script stops SpamGuard, takes its blocking rules (names starting `spamguard:`) back out of openHop, and removes its program, config, data and services. openHop, its settings and any rules you made yourself are left alone.

- `--keep-evidence` keeps the evidence log in `/var/lib/openhop_spamguard/evidence`.
- `--undo-speed-fix` also puts openHop's original packet-count setting back. Otherwise the speed fix stays, as it only makes openHop faster.
- If you chose 7 days of packet history at install, openHop keeps that. To go back to its default, set `sqlite_cleanup_days: 31` in `/etc/openhop_repeater/config.yaml` and restart openHop.

On versions before 5.8.3, which don't have `uninstall.sh`, run it from a fresh download:

```
git clone https://github.com/flackrat/openhop-spamguard.git /tmp/sg && sudo bash /tmp/sg/uninstall.sh
```

</details>

<details>
<summary><b>Evidence log and replay</b></summary>

Switch on **Keep an evidence log** in Advanced > Detection settings. SpamGuard then writes one line per channel message to `/var/lib/openhop_spamguard/evidence/` (one file per day, kept 7 days by default). Each line records the route, sender, text, every spam signal, which rule caught it, and your **This is spam** / **Not spam** answers. Block changes and settings are recorded too. A restart never writes the same message into the log twice.

Download it from Advanced > Evidence log. **Names scrambled** replaces every name and @mention with a code (keeping its spam score and shape), so it can be shared safely.

Replay a log with different settings to see what would have been caught, missed or wrongly blocked. On the older install it's already on the Pi; otherwise use a copy of this repository (`python3 replay.py ...`, with `pycryptodome` and `pyyaml` installed):
```
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py spamguard-evidence.jsonl --details
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py spamguard-evidence.jsonl --set dedupe_seconds=600
```
The more messages you label with the two buttons, the more useful the replay report is.

</details>

<details>
<summary><b>Rotating-identity protection</b></summary>

- The protection needs history: SpamGuard learns normal routes as it runs (kept for 7 days by default). Right after installing, few repeaters are "known", so a rotation block may also hold back a genuine new repeater on that route until you allow it.
- The protection only triggers on strong spam signs, never on ordinary traffic from new repeaters, and never blocks a route that people who've been chatting for a while depend on.
- The rules are placed after your own openHop rules, so the "let through" exceptions never override anything you set up.
- Because of what openHop's rules can express, a rotation block can occasionally hold back a genuine message on a similar route. Anything that looks genuine shows under **Possibly genuine** with a **Let through** button.

</details>

<details>
<summary><b>Requirements and tested systems</b></summary>

- **Plugin (recommended):** openHop 1.1.2 or later with its plugin manager running, however openHop is installed. **Older install:** openHop installed natively on Debian-style Linux with systemd, plus `curl` for updates (both standard on Raspberry Pi OS). **Docker:** any host running openHop in Docker; images for 64-bit and 32-bit Pi and for PCs (see [docs/docker.md](docker.md)).
- **Hardware:** a Raspberry Pi 3 or better. A Pi Zero 2 W should cope but hasn't been tested.
- **Software:** Python 3.9 or newer, which openHop already provides. The only libraries are pycryptodome and PyYAML, which openHop already uses. No internet needed apart from the optional update check and map directory.
- **Space:** about 125 KB to download and under 1 MB installed. The working file (about 150 KB) is saved at most every 5 minutes unless something important changes, about 33 MB of writes a day; openHop's own packet database writes far more, which is why the installer offers to keep 7 days of packet history. The evidence log is off unless you turn it on, then about 1 to 3 MB a day kept 7 days (allow 10 to 20 MB). Everything else it remembers is capped and forgotten after a while. A "High Endurance" or A2 SD card is a good idea for any always-on Pi.
- **Memory and CPU:** about 50 MB of memory at its busiest in a three-hour attack simulation, a few milliseconds per check, at most about one check a second however busy the mesh gets. The older install runs at lower priority than openHop, with memory limits of 250 MB (soft) and 400 MB (hard).
- **Limits on what it writes into openHop:** "Most rules at once" defaults to 300 and can't go above 500, covering every rule SpamGuard writes. Text blocks last at most a week; your own rules are never changed.
- **Tested** on Raspberry Pi OS (32-bit, Pi 3) in daily use, as the older install and as the plugin on openHop 1.1.5, and with openHop 1.1.5 on Ubuntu 24.04 (x86_64) as the plugin, the older install moved to the plugin, and a Docker container. Python 3.10 to 3.13. Works with 1-, 2- and 3-byte path hashes and with hashtag channels (add them on the Channels page).

</details>

<details>
<summary><b>Limits</b></summary>

SpamGuard only controls what **your** repeater forwards. People within range of the spammer will still hear them, so the more repeaters near the source that filter, the better. SpamGuard can't read private channels or direct messages unless you add the channel key.

**Repeater blocks match the repeater anywhere on a message's route.** openHop's rules can't yet say "this message *started* at repeater X", only "repeater X appears somewhere in its route". So a genuine message that merely passes through a blocked repeater, or comes from another repeater sharing its short code, can be held too. SpamGuard softens this by letting known people through, ending repeater blocks soon after the spam stops, and listing anything that looks genuine under **Possibly genuine** with a **Let through** button. A first-hop field that would fix this properly has been requested from openHop in [issue #519](https://github.com/openhop-dev/openhop_repeater/issues/519); a 👍 there helps. SpamGuard will use the field once openHop has it.

</details>
