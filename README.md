# openHop SpamGuard, with FloodGuard

![version](https://img.shields.io/github/v/release/flackrat/openhop-spamguard)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15768/badge)](https://www.bestpractices.dev/projects/15768)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/flackrat/openhop-spamguard/badge)](https://scorecard.dev/viewer/?uri=github.com/flackrat/openhop-spamguard)
[![Tests](https://github.com/flackrat/openhop-spamguard/actions/workflows/tests.yml/badge.svg)](https://github.com/flackrat/openhop-spamguard/actions/workflows/tests.yml)
![CodeQL](https://github.com/flackrat/openhop-spamguard/actions/workflows/codeql.yml/badge.svg)
![Audit](https://github.com/flackrat/openhop-spamguard/actions/workflows/audit.yml/badge.svg)

> **Spam on your mesh, stopped at the door.** SpamGuard spots spam as it happens and your repeater stops passing it on. No block lists to keep up; regulars carry on chatting.
>
> **FloodGuard** (inside SpamGuard, with its own version number) holds back far-travelled flood packets of any kind when your radio gets too busy. Direct messages are never touched.

SpamGuard runs inside [openHop](https://docs.openhop.dev/) as a plugin. It watches the channel messages and airtime your repeater hears and tells openHop not to pass spam and floods on. What it blocks is spam *behaviour*, never people or opinions.

> ### Quick start: five minutes, the plugin way
> You need a repeater running **openHop 1.1.2 or later** (check under System in openHop's dashboard). This is the recommended way for everyone; you can skip the other install options further down.
>
> 1. **Download** the file ending `-py3-none-any.whl` from the [latest release](https://github.com/flackrat/openhop-spamguard/releases/latest).
> 2. **Install it:** in openHop's dashboard go to **System > Plugins > Install wheel** and choose that file.
> 3. **Make a token:** openHop dashboard > **System > API Tokens** > create one, and copy it.
> 4. **Give SpamGuard the token:** on the Plugins page press **Config** in SpamGuard's row, paste the token into `api_key`, press **Save**, then **Enable**.
> 5. **Open it:** press **Open** in SpamGuard's row. It starts in **Monitor**, which only shows what it *would* stop. After a day, press **Protect** (or let it switch itself once it's sure).
>
> That's it. Updates are one press of **Update** on SpamGuard's page. Stuck? See [the full plugin guide](docs/openhop-plugin.md).

**Useful links:** [found a security problem?](SECURITY.md) · [want to help?](CONTRIBUTING.md) · [the two libraries it uses](requirements.txt) · [what changed, and when](CHANGELOG.md) · [words explained](docs/glossary.md)

## New to MeshCore?

How spam works on MeshCore, and the words used here: see [the glossary](docs/glossary.md).

## Why it's different

Most MeshCore spam tools either hide spam on your own phone, while the mesh still carries it to everyone else, or give repeater owners rules to write and keep up to date by hand. SpamGuard decides for itself, at the repeater, so spam is stopped before it spreads to everyone downstream. SpamGuard learns who your regulars are, so they still get through even when spam arrives the same way. A watch-only mode comes first, showing what it *would* stop before anything is stopped, and any decision can be undone with one press.

## What it does

**SpamGuard: channel spam**
- **Campaigns:** the same text under made-up or rotating names, even disguised.
- **Where spam enters:** blocked at that repeater, with regulars still let through.
- **Copies and repeats:** copy-paste floods, one name repeating itself (quickly or all day), and replays of old messages.
- **Ways round a filter:** made-up codes on the end, rotating mentions, the same link reworded, bursts, link campaigns across names, and copied names.
- **Lockdown:** in a heavy attack, only known people get through for a while.

**FloodGuard: airtime**
- **Floods of any packet type**, judged by how busy the radio is, not who sent them. Direct messages and known people always get through.
- **Learns your mesh** for three days, then sets and keeps its own limits.
- **Hop limits** like MeshCore's `flood.max.unscoped` and `flood.max.advert`.
- **Damaged copies** counted, and optionally not passed on.
- **Interference watch**, with a record of each episode.

**Principles**
- **Spam, not opinions:** it stops how spam is sent, never what people say.
- **Wardriving privacy** (optional), **settings profiles**, self-repair and one-press updates.

![SpamGuard's Overview: mode, protection level and the spam numbers, each of which opens the matching messages (example data)](docs/screenshot-overview.png)

![Messages: every channel message in one quarantine list, with what SpamGuard did and why (example data)](docs/screenshot-messages.png)

![The protection level slider, with what each level would have held on this repeater's own traffic (example data)](docs/screenshot-level.png)

![The Spam sources map: where spam entered the mesh, with a repeat spammer shown as one sender (example data)](docs/screenshot-sources.png)

![FloodGuard's page while it contains a flood (example data)](docs/screenshot-floodguard.png)

_Example data: names and numbers are made up._

## Install

The [quick start](#quick-start-five-minutes-the-plugin-way) at the top is all most people need. This section has the same steps with a little more detail, then the other ways to install for older setups.

**SpamGuard runs as an openHop plugin**, installed from openHop's own dashboard. The plugin works however openHop is installed (directly on a Pi, in Docker, on Unraid or as a Home Assistant add-on) and needs openHop 1.1.2 or later. A Raspberry Pi 3 is plenty; see **Requirements** under Advanced for space, memory and what's been tested.

1. Download `openhop_spamguard-<version>-py3-none-any.whl` from the [latest release](https://github.com/flackrat/openhop-spamguard/releases/latest).
2. In openHop's dashboard go to **System > Plugins > Install wheel** and pick that file.
3. Create an openHop API token (openHop dashboard > System > API Tokens). In SpamGuard's row on the Plugins page press **Config**, paste the token into `api_key`, press **Save**, then press **Enable**.
4. Press **Open** in SpamGuard's row to go to its page (or open `http://<your-repeater>:8091/`). Leave it in **Monitor** for a day (it shows what it *would* stop), then switch to **Protect**. If you don't come back, it switches itself to Protect once it has watched for a day and seen enough spam (the Overview shows when, with a **Stay in Monitor** button).

Full guide, including openHop in Docker: [docs/openhop-plugin.md](docs/openhop-plugin.md). New to openHop? See [docs/openhop-fresh-install.md](docs/openhop-fresh-install.md).

**Already running SpamGuard the older way?** The old version's page offers **Move to the plugin**: one press installs the plugin, carries over your settings, blocks and known people, and switches the old copy off once the plugin has taken over. Only one SpamGuard can look after a repeater at a time, and each copy checks for another before changing anything.

<details>
<summary><b>Other ways to install (older openHop, or a separate container)</b></summary>

**openHop older than 1.1.2, installed directly on a Pi:** update openHop if you can. If not, install SpamGuard as its own service:

```
git clone https://github.com/flackrat/openhop-spamguard.git
cd openhop-spamguard
sudo bash install.sh
sudo sed -i 's/PASTE_OPENHOP_API_TOKEN_HERE/YOUR_TOKEN/' /etc/openhop_spamguard/config.yaml
sudo systemctl start openhop-spamguard
```

Step-by-step guide and troubleshooting: [docs/install-and-troubleshooting.md](docs/install-and-troubleshooting.md). Once openHop is updated, use **Move to the plugin** on SpamGuard's page.

**A separate Docker container** next to openHop: [docs/docker.md](docs/docker.md). The plugin is simpler for most people, as it needs no container of its own.

</details>

## What to expect

SpamGuard learns from your mesh, so it gets better the longer it runs.

- **A few copies of each brand-new spam wave get through** while it confirms it's a campaign. After that the wave is blocked, and if it comes back later it's stopped from the first copy.
- **Your regulars become known** and are always let through. For the first day or two a genuine newcomer is more likely to be held, so open **Messages**, choose **Held**, and press **Let it through** on their message; they're let through straight away.
- **Restarts and updates keep everything it has learnt.**

## Everyday use

| You want to... | Do this |
|---|---|
| Let a genuine person through | Open **Messages**, choose **Held** (or click "Possibly genuine held" on the Overview), then **Let it through** |
| See what SpamGuard stopped, and why | Click **Spam stopped** on the Overview, or open **Messages** |
| Make it gentler or tougher | Slide the **Protection level** on the Overview; open "What this level would have done" to see the effect on your own traffic |
| Stop something it missed | In **Messages**, open it and press **Stop copies like this** |
| Ride out a heavy attack | Press **Lockdown** at the bottom of Blocks (30 min to 2 hours, ends by itself) |
| See where spam comes from | Open **Spam sources** in the menu |
| Pause all blocking | Press **Pause** on the Overview |
| Start over with a clean slate | Advanced > Settings > **Start again from scratch** |
| Clear the charts and spam map | Advanced > Settings > **Clear spam history** |
| Update | Press **Update** when the page says a new version is out |
| Remove it | Plugin: press **Pause**, wait a minute, then uninstall it in openHop (System > Plugins). Older install: `sudo bash /opt/openhop_spamguard/uninstall.sh` |

## What SpamGuard blocks, and what it doesn't

A repeater is shared: anything it refuses to pass on disappears for everyone downstream, and they can't see why. So SpamGuard judges **behaviour, never opinions or people**.

- **SpamGuard blocks:** the same text sent under several names, made-up or disguised names, floods of repeats (including one name posting the same message again and again), and repeaters injecting spam campaigns.
- **FloodGuard looks only at how packets travel:** flood or direct, how many hops they've come, and how busy the radio is. Never at who sent them or what they say, and only while a flood is actually swamping the airtime.
- **SpamGuard doesn't block** what someone says, or a named person for their views. Even the repeat guard only holds back *further copies of the repeated message*, for an hour; anything new that person says still goes out.
- **Blocking a particular person is your app's job, not the repeater's.** There's deliberately no "block this person" button. MeshCore apps and sites let each user block or hide a sender, repeater or channel for themselves. Blocking there only changes what *you* see, and the mesh still carries the message, so it's the right place for "I don't want to read this person". SpamGuard deals with behaviour that harms everyone's channel, at the repeater, so it never travels further.
- **There is no under-18 mode**, because a repeater can't tell anyone's age and a language filter wouldn't catch the real risks. [Protecting young people on MeshCore](docs/protecting-young-people.md) explains what works better, including a private channel for a youth group.
- **"This is spam" and text blocks are for spam content**, not for silencing a point of view. Every automatic block expires once the spam stops.

## Advanced

Every setting, the map, other ways to install, replaying an evidence log, health checks and more: see [the advanced guide](docs/advanced.md).

## Accessibility

The web page is built to WCAG 2.1 AA and works fully with a keyboard and screen readers. The **Display** page in the menu lets each person choose larger text, light or dark colours, high contrast and reduced motion; those choices are saved in their own browser. Every chart has a table of its numbers, and the spam map's circles can be reached with Tab and opened with Enter. If something doesn't work for you, please open an issue.

## For developers

SpamGuard needs only two libraries, [pinned in `requirements.txt`](requirements.txt) with checksums: pycryptodome (to read channel messages) and PyYAML (to read its config file). The tools for tests and checks have their own locked lists in `requirements/`. To report a security problem privately, see [SECURITY.md](SECURITY.md); to suggest or send a change, see [CONTRIBUTING.md](CONTRIBUTING.md).

`bash tests/run_all.sh` runs the test suite against a fake openHop and openHop's real rule engine (add `--slow` for the Pi-sized stress test). The suite includes `tests/redteam.py`, a simulated four hours of chat and fourteen kinds of spam attack that fails if too much spam gets through or too many genuine messages are held; nothing in it talks to a real repeater, and all its data is made up. The whole suite, plus a lint, a privacy check and a dependency review, [runs automatically on GitHub](https://github.com/flackrat/openhop-spamguard/actions/workflows/tests.yml) for every pull request and every change to `main`, and `main` only accepts changes through a pull request whose tests have passed, so nothing reaches a release untested. `tools/fieldcheck.js` is a read-only self-check you can paste into the browser console with the SpamGuard page open: it summarises the last 12 hours from SpamGuard's own status and evidence log (whether it stayed up, whether any blocked spam was forwarded or any genuine message dropped, and what the spam map shows). The script only ever reads the log with names scrambled, and never the lists of people in the status.

## Other openHop plugins

SpamGuard is one of a growing number of plugins for openHop Repeater. Others worth a look:

| Plugin | What it does |
|---|---|
| [txmesh](https://github.com/zfouts/openhop-txmesh-plugin) | Connects your repeater to the txme.sh network, reporting mesh activity and relaying bot replies |
| [Telemetry](https://codeberg.org/vanous/openhop-telemetry-plugin) | Collects voltage and temperature from MeshCore repeaters |
| [Prometheus](https://github.com/openhop-dev/openhop-prometheus-plugin) | Exports your repeater's telemetry as Prometheus metrics, with a small built-in dashboard |
| [Nomad](https://github.com/openhop-dev/openhop-nomad-plugin) | Bridges a dedicated repeater companion identity to Project N.O.M.A.D. |

Know another one? Suggestions are welcome as an issue.

## Licence

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later), see [LICENSE](LICENSE). Copyright (c) 2026 Flackrat.

You're free to use, study, change and share SpamGuard. If you share a copy or a changed version, or let people use a changed version over a network (for example as a web page), you must make its full source code available under the same licence and keep the copyright notice. Versions up to 5.32 were released under the MIT licence; from 5.33 on SpamGuard is AGPL. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Disclaimer

- **No warranty.** SpamGuard is provided "as is", without warranty of any kind, express or implied. To the extent permitted by law, the author and contributors accept no liability for any loss or damage arising from its use, including missed spam, genuine messages being blocked, repeater downtime or data loss. See the licence (AGPL-3.0, sections 15 and 16) for the full terms. Nothing in this disclaimer limits any liability that cannot be limited by law.
- **You run it, you decide.** SpamGuard changes what your own repeater forwards. You choose its mode and settings and you are responsible for how you operate your repeater. Start in Monitor mode and check what it would block.
- **Radio rules.** SpamGuard doesn't transmit or change radio settings, but the repeater it runs alongside must be operated within the rules for your country and band (in the UK, Ofcom's licence-exempt short-range device rules). Compliance is the operator's responsibility.
- **Personal data.** SpamGuard reads Public and hashtag channel messages your repeater receives, which anyone with a MeshCore device can read. Recent messages, sender names and routes are kept in memory and, only if you switch the evidence log on, in files on your own Pi (7 days by default). Nothing is sent anywhere except the optional once-a-day version check to GitHub, the download from GitHub when you press Update, and, only if you turn it on, a once-a-day download of the public MeshCore map's repeater list. If you keep or share logs, you are responsible for complying with data-protection law where you are (for example the UK GDPR); use the "names scrambled" export when sharing.
- **Changes to openHop.** The optional `tune-openhop.sh` edits one setting inside your openHop installation, with your consent and a backup. Use it at your own risk; it can be undone with `--undo`.
- **Independent project.** SpamGuard is not affiliated with, endorsed by or supported by openHop, MeshCore or their developers. Product names are used only to describe compatibility and belong to their respective owners.
- **Not professional advice.** The documentation describes how the author set things up; it isn't legal, regulatory or professional advice.
