# SpamGuard: install and troubleshooting guide

_For SpamGuard on openHop Repeater · October 2026_

## Before you start

SpamGuard installs in about 10 minutes on a Pi that already runs openHop Repeater natively (not in Docker). You need SSH access to the Pi and an openHop API token. If openHop isn't installed yet, follow [openHop Repeater: prerequisites and fresh install](openhop-fresh-install.md) first.

Commands in this guide use two placeholders. Swap in your own values when you type them, without the `< >`.

| Placeholder | Means | Example |
|---|---|---|
| `<pi-ip>` | Your Pi's address on your network | `192.168.1.50` |
| `<user>` | The username you log in to the Pi with | `pi` |

To find `<pi-ip>`, run `hostname -I` on the Pi (use the first address), or look at your router's list of connected devices. Many networks also accept the Pi's hostname with `.local` on the end instead, for example `raspberrypi.local`.

The address only matters for reaching the Pi from your PC or phone. SpamGuard talks to openHop on `127.0.0.1` inside the Pi, so if the Pi's IP changes nothing breaks; you just use the new address. To stop it changing, reserve the address for the Pi in your router's DHCP settings.

| What | Address |
|---|---|
| openHop dashboard | `http://<pi-ip>:8000` |
| SpamGuard page | `http://<pi-ip>:8091` |

On Windows, PuTTY gives you `ssh` access and `pscp` for copying files; WinSCP is a drag-and-drop alternative. Commands below are typed on the Pi unless they say "on your PC".

## Install, step by step

A fresh install ends with SpamGuard running in Monitor mode, so nothing is blocked until you choose Protect.

1. **Create an openHop API token.** In the openHop dashboard go to System > Configuration > Access > API Tokens, create one and copy it. It is shown only once and gives full admin access, so treat it like a password.
2. **Download and install** (on the Pi):

    ```
    cd ~
    git clone https://github.com/flackrat/openhop-spamguard.git
    cd openhop-spamguard
    sudo bash install.sh
    ```

    The installer asks two questions about openHop. Answer **y** to both unless you have a reason not to. The first applies the openHop speed fix; the second keeps 7 days of packet history instead of 31. Both are explained under "If openHop falls behind" below.

3. **Add the token to the config** (replace `YOUR_TOKEN`; the quotes stay):

    ```
    sudo sed -i 's/PASTE_OPENHOP_API_TOKEN_HERE/YOUR_TOKEN/' /etc/openhop_spamguard/config.yaml
    sudo grep api_key /etc/openhop_spamguard/config.yaml
    ```

4. **Start SpamGuard and check it is running:**

    ```
    sudo systemctl start openhop-spamguard
    systemctl is-active openhop-spamguard
    curl -s http://127.0.0.1:8091/health
    ```

    `active` and `"state": "ok"` mean it is working.

5. **Open the page** at `http://<pi-ip>:8091` and check the Health panel says Healthy and "Restart if it hangs" is on.
6. **Leave it in Monitor for a day.** Messages it would have stopped are tagged "Would be stopped". Press **Not spam** on anything genuine, **This is spam** on anything it missed.
7. **Switch to Protect** on the page when you are happy it only catches spam.

Optional: Advanced > Detection settings > **Keep an evidence log**, so detection can be tuned against your real traffic later.

## Updating

SpamGuard checks GitHub for a new release once a day and shows it in the **Updates** section of its page, with what's new. Nothing changes until you press **Update**. Your token, mode, settings, blocks and learnt routes are kept, and if the new version doesn't start the previous one is put back automatically. Press **Ctrl+F5** afterwards so the browser loads the new page.

To turn the daily check off: Advanced > Updates > Look for new versions > Only when I press Check.

From the command line:

```
sudo bash /opt/openhop_spamguard/update.sh --check          # installed and latest versions
sudo bash /opt/openhop_spamguard/update.sh                  # install the latest release
sudo bash /opt/openhop_spamguard/update.sh --version v5.8   # a particular release (also to go back)
cat /var/lib/openhop_spamguard/update-status.json           # result of the last update
```

Or from the folder you cloned: `cd ~/openhop-spamguard && git pull && sudo bash install.sh`.

Upgrading from a version installed from a .tar.gz file: install once with the git commands above. Your config and blocks are kept.

## Everyday commands

All run on the Pi; the `sudo` ones ask for your password.

| To do this | Run |
|---|---|
| Is it running? | `systemctl is-active openhop-spamguard` |
| Is it healthy? | `curl -s http://127.0.0.1:8091/health` |
| Full service status | `sudo systemctl status openhop-spamguard --no-pager` |
| Restart it | `sudo systemctl restart openhop-spamguard` |
| Stop / start | `sudo systemctl stop openhop-spamguard` / `sudo systemctl start openhop-spamguard` |
| Times systemd restarted it | `systemctl show openhop-spamguard -p NRestarts` |
| Watch the log live (Ctrl+C to stop) | `sudo journalctl -u openhop-spamguard -f` |
| Last 50 log lines | `sudo journalctl -u openhop-spamguard -n 50 --no-pager -l` |
| Only decisions and errors, last hour | `sudo journalctl -u openhop-spamguard --since "1 hour ago" --no-pager -l \| grep -E "INFO\|WARNING\|ERROR"` |
| Edit the config | `sudo nano /etc/openhop_spamguard/config.yaml`, then restart |
| Show the token in the config | `sudo grep api_key /etc/openhop_spamguard/config.yaml` |
| SpamGuard rules openHop holds | `curl -s http://127.0.0.1:8091/rules` |
| Is openHop running? | `systemctl is-active openhop-repeater` |
| Restart openHop | `sudo systemctl restart openhop-repeater` |

The page's footer line "last checked … ago" is the quickest check: "just now", updating every few seconds, means SpamGuard is working.

## Troubleshooting

Start with the Health panel on the page and the last 50 log lines; most problems name themselves there.

| Symptom | Likely cause | Fix |
|---|---|---|
| Page won't load | Service stopped, or wrong address/port | `systemctl is-active openhop-spamguard`; if not active, `sudo systemctl start openhop-spamguard` and read the log. Use port 8091 and the Pi's current IP. |
| Page shows an old version after updating | Browser cache | Press Ctrl+F5. |
| Update button says the updater isn't set up | Installed before v5.8 | Install once from GitHub by hand (see Install); the button works from then on. |
| "Couldn't reach GitHub" | Pi offline, or GitHub blocked | Updates need internet; spam blocking doesn't. |
| "openHop refused the API key (HTTP 401/403)" | Token wrong, missing or revoked | Check with `sudo grep api_key /etc/openhop_spamguard/config.yaml`; create a new token in openHop if needed, update it, restart SpamGuard. |
| "Cannot reach openHop" for a minute after boot or restart | openHop still starting | Nothing: SpamGuard waits and connects by itself. |
| "Cannot reach openHop" that persists | openHop stopped or busy | `systemctl is-active openhop-repeater`; restart it with `sudo systemctl restart openhop-repeater`. |
| `grep: ... Permission denied` on the config | The config is readable by root only (it holds the token) | Put `sudo` in front. |
| Times on the page are an hour or more out | Pi's time zone not set (it defaults to UTC) | See Pi housekeeping below. |
| Newest message is old | Quiet channel, or checking stopped | Check the footer "last checked"; if it is not "just now", restart SpamGuard and send the log. |
| `ConnectionResetError` in older logs | A phone closed the page mid-refresh | Harmless; v5.1.1 and later no longer log it. |
| "Restart if it hangs: off" on the page | Old service settings | Re-run `sudo bash install.sh` from the package folder. |
| Genuine people being blocked | A rule too broad for your traffic | Press **Not spam** on their message, remove the block, or choose Relaxed sensitivity. |
| Spam getting through | Spam doesn't match the current signs yet | Press **This is spam**; try Strict during an attack; keep the evidence log on for tuning. |
| Restart command doesn't return | Service stuck stopping | In a second window: `sudo systemctl kill -s KILL openhop-spamguard` then `sudo systemctl start openhop-spamguard`. |

If something looks wrong, collect these three and send them for diagnosis:

```
sudo systemctl status openhop-spamguard --no-pager
sudo journalctl -u openhop-spamguard -n 80 --no-pager -l
curl -s http://127.0.0.1:8091/health
```

**Emergency stop:** Pause on the page removes every SpamGuard rule from openHop at once. If the page is unreachable, `sudo systemctl stop openhop-spamguard` stops it, but its existing blocks stay in openHop. Remove them in openHop's Policies page (their names start with `spamguard:`), or start SpamGuard again and press Pause.

## Known people and Lockdown

| Symptom | Check / fix |
|---|---|
| A regular's messages are held by a repeater block | They aren't known yet (they need one genuine message on another route). Press **Not spam** on their message: that trusts them and lets them through at once. |
| A newcomer's link was held | Links from unknown names are held during spam campaigns. Press **Not spam**, or set Advanced > Known people > Hold links to Never. |
| Lockdown is holding too many people | Press **End lockdown**. The page shows how many names SpamGuard knows; with only a few, most people are held. |
| One named account keeps posting abuse | In Advanced, press **Block sender** on one of its messages (or type the name under Block something yourself). It matches the exact name, emoji included. |
| openHop shows a policy object called `spamguard` | That's the known-people list. SpamGuard keeps it up to date and the uninstaller removes it. |

## If openHop falls behind

On a small Pi (a Pi 3, say) with a large packet database, openHop can fall minutes behind saving the packets it hears. SpamGuard reads that saved list, so it then sees spam minutes late and a whole wave gets through before a block starts. The Health panel shows this as **openHop delay**. A few seconds is normal; minutes means openHop is struggling.

The cause is inside openHop. Every time it saves a packet it recounts every packet it has stored, and keeps that answer for only 3 seconds. The count is only used for the graphs, which are written once a minute. SpamGuard's `tune-openhop.sh` makes openHop keep the count for 60 seconds instead, which changes nothing you can see, and offers to keep 7 days of packet history instead of 31 so the database stays small.

```
sudo bash /opt/openhop_spamguard/tune-openhop.sh            # apply (asks before each change)
sudo bash /opt/openhop_spamguard/tune-openhop.sh --check    # just report
sudo bash /opt/openhop_spamguard/tune-openhop.sh --undo     # put openHop's original value back
```

An openHop upgrade puts the old value back. When that happens the Health panel says "openHop's speed fix isn't in place": run the script again. Advanced view shows **openHop speed fix: on/off** in the Health panel.

To see what openHop is busy with, if it is still slow:

```
top -b -n1 | head -12
sudo /opt/openhop_repeater/venv/bin/pip install py-spy
sudo /opt/openhop_repeater/venv/bin/py-spy dump --pid $(pgrep -f repeater.main) | grep -A4 "(active)"
```

SpamGuard also remembers spam texts sent under made-up names for 7 days (Advanced > Timing), so a text the spammer brings back is stopped from its first copy even while openHop is behind.

## Evidence log and replay

The evidence log records every channel message with its spam signals and your labels; download it from Advanced > Evidence log, choosing **names scrambled** before sharing it.

Command-line equivalents:

```
# where the daily files live, and their size
ls -lh /var/lib/openhop_spamguard/evidence/

# download the last 7 days, names scrambled, to your home folder
curl -s "http://127.0.0.1:8091/evidence?days=7&scramble=1" -o ~/sg-evidence.jsonl
```

Copy it to your PC (on your PC):

```
pscp <user>@<pi-ip>:sg-evidence.jsonl .
```

Replay it with different settings to see what would have been caught, missed or wrongly blocked:

```
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py ~/sg-evidence.jsonl
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py ~/sg-evidence.jsonl --details
/opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py ~/sg-evidence.jsonl --sensitivity strict --set dedupe_seconds=600
```

If you set a page password (`listen_api_key`), add `-H "X-API-Key: YOUR_PASSWORD"` to the curl command.

## Pi housekeeping

A correct clock and time zone keep the page's times, the evidence log and the daily files lined up with real time.

```
# check time zone and clock sync
timedatectl

# find your zone name, e.g. Europe/London, Europe/Dublin, America/New_York
timedatectl list-timezones | grep -i london

# set it (daylight saving switches automatically)
sudo timedatectl set-timezone Europe/London
sudo timedatectl set-ntp true
sudo systemctl restart openhop-repeater openhop-spamguard
```

Back up SpamGuard's config and state before big changes (blocks, learnt routes, settings, trusted lists):

```
sudo tar czf ~/spamguard-backup-$(date +%F).tar.gz /etc/openhop_spamguard /var/lib/openhop_spamguard/state.json
```

Restore by stopping SpamGuard, unpacking that file over `/` with `sudo tar xzf ~/spamguard-backup-DATE.tar.gz -C /`, then starting it again.

Useful Pi checks: `vcgencmd measure_temp` (temperature), `df -h /` (disk), `free -h` (memory), `uptime` (load).

## Removing SpamGuard and file locations

```
sudo bash /opt/openhop_spamguard/uninstall.sh
```

It stops SpamGuard, takes its rules back out of openHop, and removes everything listed below. Your own openHop rules and settings are left alone. Add `--keep-evidence` to keep the evidence log, or `--undo-speed-fix` to put openHop's original packet-count setting back as well.

If your version doesn't have `uninstall.sh` (before 5.8.3), run it from a fresh download:

```
git clone https://github.com/flackrat/openhop-spamguard.git /tmp/sg && sudo bash /tmp/sg/uninstall.sh
```

If the uninstaller says it couldn't update openHop's rules (for example because the API token was already deleted), remove any rule whose name starts with `spamguard:` in the openHop dashboard, then restart openHop.

| What | Where |
|---|---|
| Program, web page, replay tool, openHop speed-fix script | `/opt/openhop_spamguard/` |
| Config (token, mode, sensitivity) | `/etc/openhop_spamguard/config.yaml` |
| Old config kept by an upgrade | `/etc/openhop_spamguard/config.yaml.old` |
| Blocks, learnt routes, page settings | `/var/lib/openhop_spamguard/state.json` |
| Evidence log (one file per day) | `/var/lib/openhop_spamguard/evidence/` |
| Services | `/etc/systemd/system/openhop-spamguard.service`, `openhop-spamguard-update.path`, `openhop-spamguard-update.service` |
| SpamGuard's rules (inside openHop) | `/etc/openhop_repeater/policy.yaml`, names starting `spamguard:`, plus the `spamguard` object (known people) |
| Log | `sudo journalctl -u openhop-spamguard` |

---

SpamGuard is provided "as is", without warranty, under the MIT licence. You are responsible for how you operate your repeater and for any message logs you keep. It is an independent project, not affiliated with openHop or MeshCore. See the [Disclaimer](../README.md#disclaimer).
