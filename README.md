# openHop SpamGuard

![version](https://img.shields.io/github/v/release/flackrat/openhop-spamguard)

**Stops MeshCore channel spam at your [openHop](https://docs.openhop.dev/) repeater, automatically.** It runs on the same Pi as openHop, watches the channel messages your repeater hears, and tells openHop not to pass spam on. It blocks spam *behaviour*, never people or opinions.

## What it does

- **Catches spam campaigns:** the same text sent under made-up, rotating names, even with words added, look-alike letters or emoji tricks.
- **Finds where spam enters the mesh** and blocks it there, while still letting your regulars through.
- **Stops copy-paste floods:** the first copy gets through, copies under other names don't.
- **Lockdown button** for a heavy attack: for a while, only people it already knows get through.
- **Looks after itself:** a simple web page, automatic self-repair, gentle on SD cards, and updates only when you press Update.
- **Speeds up openHop on small Pis** with an optional one-line fix the installer offers.

![SpamGuard's web page (example data)](docs/screenshot.png)

_Example data: names and numbers are made up._

## Install

You need openHop installed **natively** on a Raspberry Pi or other Debian-style Linux (not the Docker version), and an openHop API token: openHop dashboard > System > Configuration > Access > API Tokens. New to openHop? See [docs/openhop-fresh-install.md](docs/openhop-fresh-install.md).

On the Pi:

```
git clone https://github.com/flackrat/openhop-spamguard.git
cd openhop-spamguard
sudo bash install.sh
```

Answer **y** to the installer's two questions about openHop's speed. Then add your token and start it:

```
sudo sed -i 's/PASTE_OPENHOP_API_TOKEN_HERE/YOUR_TOKEN/' /etc/openhop_spamguard/config.yaml
sudo systemctl start openhop-spamguard
```

Open `http://<your-pi>:8091/`. Leave it in **Monitor** for a day (it shows what it *would* stop), then switch to **Protect**.

Step-by-step guide and troubleshooting: [docs/install-and-troubleshooting.md](docs/install-and-troubleshooting.md).

## What to expect

SpamGuard learns from your mesh, so it gets better the longer it runs.

- **A few copies of each brand-new spam wave get through** while it confirms it's a campaign. After that the wave is blocked, and if it comes back within 7 days it's stopped from the first copy.
- **It gets to know your regulars** and always lets them through. For the first day or two a genuine newcomer is more likely to be held: press **Not spam** on their message and they're let through straight away.
- **Restarts and updates keep everything it has learnt.**

## Everyday use

| You want to... | Do this |
|---|---|
| Let a genuine person through | Press **Let through** under "Possibly genuine, held", or **Not spam** on their message |
| Stop something it missed | Press **This is spam** on the message |
| Ride out a heavy attack | Press **Lockdown** (30 min to 2 hours, ends by itself) |
| See where spam comes from | Open **Spam sources** in the menu |
| Pause all blocking | Press **Pause** on the Overview |
| Update | Press **Update** when the page says a new version is out |
| Remove it | `sudo bash /opt/openhop_spamguard/uninstall.sh` |

## What SpamGuard blocks, and what it doesn't

A repeater is shared: anything it refuses to pass on disappears for everyone downstream, and they can't see why. So SpamGuard judges **behaviour, never opinions or people**.

- **It blocks:** the same text sent under several names, made-up or disguised names, floods of repeats, and repeaters injecting spam campaigns.
- **It doesn't block** what someone says, or a named person for their views. There's deliberately no "block this person" button: muting someone is each user's choice, in their own MeshCore app.
- **"This is spam" and text blocks are for spam content**, not for silencing a point of view. Every automatic block expires once the spam stops.

## Advanced

Click a heading to expand it.

<details>
<summary><b>The web page</b></summary>

- **Menu**: a side menu like openHop's own (a slide-out menu on phones). **Overview**, **Protection** (blocks, possibly genuine, Lockdown), **Monitoring** (messages, spam sources) and **System** (health, updates, help). Advanced adds campaigns, activity, settings, exceptions and the evidence log.
- **Overview**: mode, sensitivity, and the numbers at a glance: spam stopped, let through, spam's share of channel traffic, airtime saved, genuine messages held, known people. Charts show the last 24 hours, the last 7 days, and which hours of the day spam usually arrives.
- **Spam sources**: which repeaters spam arrives through, on a map (repeaters that advertise a location) and in a table with Block / Never block buttons. The map needs internet access on the device viewing the page; the table works without it.
- **Long lists** (messages, blocks, activity) show 10 at a time with **Show more**.
- **Advanced** (switch at the bottom of the menu): every setting with what it does and a "Watch out" note on its side-effects, per-block controls, per-repeater statistics, spam campaigns, exceptions (trusted senders, repeaters, texts, channels), Known people settings, the evidence log and an activity log.

</details>

<details>
<summary><b>Known people, links and Lockdown</b></summary>

SpamGuard keeps a list of names it has seen sending genuine messages (not made-up looking, not part of a spam campaign, and not arriving through a blocked repeater). It writes the list into openHop as a policy object, `@spamguard.known_senders`, with one "let known people through" rule per channel, placed after your own rules. Three kinds of block sit below that rule, so they never stop a known name:

- **Repeater blocks** block *anything passing through* the spam repeater, except known people, and end 2 hours after the spam through it stops (Advanced > Timing). People held this way who don't look like spammers are listed under **Possibly genuine, held** on the main page, with a **Let through** button. In testing on real logs the spammer's messages took a different full route every time, so blocking learnt routes one by one never caught them; this catches every one. The older "Routes starting there" and "Anything passing through" choices are still in Advanced.
- **Links from names it doesn't know** (http or www.) are held while a spam campaign is under way, by default for an hour after the last campaign activity. Advanced > Known people can make this always or never.
- **Lockdown** (button on the page): for 30 minutes to 2 hours, only known names get through on the channels SpamGuard reads. New people are held too, so it's for heavy attacks only. It ends by itself.

Replaying a day of real traffic (69 spam, 597 genuine messages): spam caught went from 58 to 65. 4 genuine messages were held: two first-time posts (a link, and a message through the spam repeater) and two from names that looked like the spammer's own joke accounts.

Things to know:

- A name counts as known after 1 genuine message by default (Advanced > Known people). Names can be faked, so a spammer who copies a regular's exact name gets past these three blocks. Text and campaign blocks still apply to everyone.
- After updating, SpamGuard starts the list from the names it heard in the last day.
- Names are forgotten after 30 days of silence. The list is in openHop's `policy.yaml`; channel names are public anyway, but bear it in mind if you share that file.

</details>

<details>
<summary><b>How the spammer might try to get round it</b></summary>

| Workaround | Countermeasure |
|---|---|
| New name every message | Names are scored for looking made-up; many new names through one repeater also triggers a block |
| Lowercase or longer random names | Name scoring ignores case and length; "word + number" names like Dave1985 stay human |
| Realistic names (Dave, Sarah...) | "Brand-new names" limit per repeater |
| Random words added to the message | Similar messages are grouped; the rule matches the shared part |
| Look-alike letters, hidden characters, l33t | Text is normalised before comparing; these tricks are themselves a spam sign; each variant is blocked |
| Posting slowly to stay under limits | A 2-hour long window catches slow spam |
| Replies to the same person (@[name]) looking alike | Mentions are ignored when comparing messages, so ordinary replies are never treated as a campaign; a campaign also needs at least two made-up, disguised or brand-new names |
| Bringing the same spam back hours or days later | Text blocks for campaigns sent under made-up names stay in openHop for 7 days (Advanced > Timing), so a returning text is stopped from its first copy |
| Copying a trusted or known person's name | Gets past repeater, link and lockdown blocks (they let known names through), but never campaign or text blocks; a trusted name from a new place is logged |
| Moving location / new routes | Repeater blocks match anything passing through, so a new route from the same repeater is caught at once; known people are let through. Text rules work from anywhere |
| Posting links from a fresh name each time | While a campaign is under way, links from names SpamGuard doesn't know are held |
| Within direct range (no repeaters) | Warning on the page; text rules and duplicate suppression still work |
| 2- or 3-byte path hashes | Routes are matched at any width; exceptions cover all widths |
| Moving to a hashtag channel | Add the channel by name; its key is worked out automatically |
| Flooding to exhaust rules | Rule cap with the oldest duplicate rules dropped first; repeater blocks are kept |
| Faking routes to frame a genuine repeater | Exact-route blocking only affects the faked route; mark your neighbours "Never block" |
| Emoji added to a random name (UD6DWREK🔥) | Names are scored with emoji removed; emoji in genuine names (Ohm🔌) don't count against them |
| Emoji sprinkled between words, different each time | Messages are compared with emoji removed; a rule requiring all the shared words catches new arrangements |
| Emoji inside words (Bu🔥ilt), invisible tag letters | Flagged as disguised text, which counts as a spam sign; normal emoji use (👍, family emoji, flags) isn't |
| Emoji-only spam, with skin-tone or colour variants | Compared by base emoji, so 💩 and 💩🏽 count as the same message |
| Repeater firmware that changes its ID, so the first hop changes every time | SpamGuard learns which repeaters normally start routes and which relay. When several never-seen first repeaters send spam through the same onward route (e.g. >B1>7E), unknown ones on that route are blocked while known ones are let through. A trusted sender arriving via a new repeater gets it let through automatically, and you can allow any repeater from the page |

</details>

<details>
<summary><b>Health and self-repair</b></summary>

The **Health** panel on the page shows whether SpamGuard is working: how long it has been running, when it last checked, whether openHop is answering, whether all its rules are in place in openHop, and how many times it has restarted. Advanced adds the Pi's temperature, memory, disk and load.

SpamGuard looks after itself:
- **Restarts if it hangs.** It checks in with systemd after every pass of its checking loop. If it stops checking in for 90 seconds, systemd restarts it. It also restarts after a crash, and never gives up.
- **Puts its rules back.** Once a minute it confirms openHop still has exactly its rules (after an openHop restart, restore or manual edit), and restores them if not. Your own rules are never touched.
- **Keeps protecting while down.** Its rules live in openHop, so blocking carries on even if SpamGuard is stopped. Blocks just don't expire or update until it's back.
- **Measures openHop's delay.** It shows how far behind real time openHop's packet list is, and warns when it is 30 seconds or more behind, because spam copies arriving in that gap get through before a block starts. Each evidence-log line also records how late SpamGuard saw the message.
- **Notices a deaf radio.** If openHop reports no new packets of any kind for 20 minutes, the Health panel warns that its radio may have stopped receiving.
- **Asks openHop for as little as possible.** It reads only packets newer than the last ones it saw, using a query openHop's database answers from its time index (older openHop versions fall back to the recent packet list).
- **Stays out of the repeater's way.** It runs at lower CPU priority than openHop and is capped at 400 MB of memory.

Quick checks from the command line:
```
systemctl is-active openhop-spamguard          # "active" = running
curl -s http://127.0.0.1:8091/health           # "state": "ok" / "warn" / "bad"
systemctl show openhop-spamguard -p NRestarts  # how many times systemd has restarted it
```
`/health` returns HTTP 200 when healthy and 503 when something is wrong, so it can be watched by a monitoring tool such as Uptime Kuma.

</details>

<details>
<summary><b>openHop running behind (speed fix)</b></summary>

On a small Pi with a large packet database, openHop can fall minutes behind saving packets. SpamGuard then sees spam late, and a wave gets through before a block starts. The Health panel shows this as **openHop delay**.

The cause is in openHop. Every time it saves a packet it recounts every packet it has stored, and keeps the answer for only 3 seconds. That count is only used for the graphs, which are written once a minute. `tune-openhop.sh` changes that 3 seconds to 60 seconds, which changes nothing you can see, and offers to keep 7 days of packet history instead of 31.

```
sudo bash /opt/openhop_spamguard/tune-openhop.sh            # apply (asks first)
sudo bash /opt/openhop_spamguard/tune-openhop.sh --check    # report only
sudo bash /opt/openhop_spamguard/tune-openhop.sh --undo     # put openHop's value back
```

An openHop upgrade puts the old value back. The Health panel then says "openHop's speed fix isn't in place"; run the script again.

</details>

<details>
<summary><b>Updating</b></summary>

SpamGuard looks for a new release once a day (you can turn that off in Advanced > Updates) and shows it in the **Updates** section of its page, with what's new. It only installs when you press **Update**. Your settings, blocks and learnt routes are kept, and if the new version doesn't start, the previous one is put back automatically.

From the command line instead:

```
sudo bash /opt/openhop_spamguard/update.sh --check          # installed and latest versions
sudo bash /opt/openhop_spamguard/update.sh                  # install the latest release
sudo bash /opt/openhop_spamguard/update.sh --version v5.9   # install a particular release (also to go back)
```

Or, from your clone: `git pull && sudo bash install.sh`.

How the button works: SpamGuard runs as an ordinary user, so it can't install software. Pressing Update leaves a request file that a small root-owned systemd service (`openhop-spamguard-update`) carries out. It only ever downloads tagged releases of this repository over HTTPS. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

</details>

<details>
<summary><b>Uninstalling</b></summary>

```
sudo bash /opt/openhop_spamguard/uninstall.sh
```

This stops SpamGuard, takes its blocking rules (names starting `spamguard:`) back out of openHop, and removes its program, config, data and services. openHop, its settings and any rules you made yourself are left alone.

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

Replay a log with different settings to see what would have been caught, missed or wrongly blocked:
```
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py spamguard-evidence.jsonl --details
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py spamguard-evidence.jsonl --set dedupe_seconds=600
```
The more messages you label with the two buttons, the more useful the replay report is.

</details>

<details>
<summary><b>Rotating-identity protection</b></summary>

- It needs history: SpamGuard learns normal routes as it runs (kept for 7 days by default). Right after installing, few repeaters are "known", so a rotation block may also hold back a genuine new repeater on that route until you allow it.
- It only triggers on strong spam signs (made-up names, disguised text or campaign copies), never on ordinary traffic from new repeaters.
- Its rules are placed after your own openHop rules, so its "let through" exceptions never override anything you set up.
- openHop can't match "exactly this route after an unknown first repeater", so the block matches any route of the same length containing those repeaters. Routes with the same repeaters in a different order are rare, but would also be held back.

</details>

<details>
<summary><b>SD card and storage</b></summary>

Everything SpamGuard keeps has a limit: learnt routes (5,000, forgotten after 7 days), known names (5,000, forgotten after 30 days of silence), the activity list (300), and the evidence log (deleted after 7 days by default, about 1-3 MB a day; off unless you turn it on). Its working file (about 150 KB) is saved at most every 5 minutes unless something important changes, about 33 MB of writes a day. openHop's own packet database writes far more, which is why the installer offers to keep 7 days of packet history. A "High Endurance" or A2 SD card is a good idea for any always-on Pi.

</details>

<details>
<summary><b>Requirements and tested systems</b></summary>

- openHop Repeater installed natively (not Docker) on Debian-style Linux with systemd; `curl` for updates. Both are standard on Raspberry Pi OS.
- Tested on Raspberry Pi OS (32-bit, Pi 3) in daily use, and with a full openHop + SpamGuard install on Ubuntu 24.04 (x86_64). Python 3.10 to 3.13.
- Works with 1-, 2- and 3-byte path hashes, and with hashtag channels (add them by name in Advanced > Exceptions > Channels).

</details>

<details>
<summary><b>Limits</b></summary>

SpamGuard only controls what **your** repeater forwards. People within range of the spammer will still hear him, so the more repeaters near the source that filter, the better. It can't read private channels or direct messages unless you add the channel key.

</details>

## Licence

MIT, see [LICENSE](LICENSE). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Disclaimer

- **No warranty.** SpamGuard is provided "as is", without warranty of any kind, express or implied. To the extent permitted by law, the author and contributors accept no liability for any loss or damage arising from its use, including missed spam, genuine messages being blocked, repeater downtime or data loss. See the MIT licence for the full terms. Nothing in this disclaimer limits any liability that cannot be limited by law.
- **You run it, you decide.** SpamGuard changes what your own repeater forwards. You choose its mode and settings and you are responsible for how you operate your repeater. Start in Monitor mode and check what it would block.
- **Radio rules.** SpamGuard doesn't transmit or change radio settings, but the repeater it runs alongside must be operated within the rules for your country and band (in the UK, Ofcom's licence-exempt short-range device rules). That is the operator's responsibility.
- **Personal data.** SpamGuard reads Public and hashtag channel messages your repeater receives, which anyone with a MeshCore device can read. It keeps recent messages, sender names and routes in memory and, only if you switch the evidence log on, in files on your own Pi (7 days by default). Nothing is sent anywhere except the optional once-a-day version check to GitHub. If you keep or share logs, you are responsible for complying with data-protection law where you are (for example the UK GDPR); use the "names scrambled" export when sharing.
- **Changes to openHop.** The optional `tune-openhop.sh` edits one setting inside your openHop installation, with your consent and a backup. Use it at your own risk; it can be undone with `--undo`.
- **Independent project.** SpamGuard is not affiliated with, endorsed by or supported by openHop, MeshCore or their developers. Product names are used only to describe compatibility and belong to their respective owners.
- **Not professional advice.** The documentation describes how the author set things up; it isn't legal, regulatory or professional advice.
