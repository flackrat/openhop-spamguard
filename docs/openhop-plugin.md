# SpamGuard as an openHop plugin

openHop has a plugin system (System > Plugins in its dashboard) that works the same whether openHop is installed directly, in Docker, on Unraid or as a Home Assistant add-on. SpamGuard can run as one of those plugins, so you don't need SSH, an installer or a separate container.

It needs **openHop 1.1.2 or later**. If System > Plugins isn't in your openHop dashboard, your openHop is older: update it with the update option in its dashboard, or `manage.sh upgrade` on the Pi, and the Plugins page appears.

Only one SpamGuard can look after a repeater at a time. Each copy checks for another before changing anything, and waits if one is already in charge, so installing the plugin next to an older install never makes them fight. To switch, use **Move to the plugin** (below).

## Moving from an older SpamGuard install

If SpamGuard is already running the older way (its own service on the Pi, or a Docker container), you don't need to do any of the steps below by hand. Update it to the latest version, then press **Move to the plugin** on its Overview page. It:

1. installs the plugin in openHop for you,
2. copies your settings and token across,
3. starts the plugin, which picks up everything the old copy has learnt (blocks, known people, charts and the map),
4. hands the repeater over, and switches the old copy off (a Docker container is left for you to remove).

The repeater stays protected the whole time, and the page carries on at the same address. The old copy's files are kept, so you can go back (see "Going back" below). The evidence log, if you had it on, stays in the old copy's folder.

## Install

1. Download `openhop_spamguard-<version>-py3-none-any.whl` from the latest [release](https://github.com/flackrat/openhop-spamguard/releases/latest). (Once SpamGuard is in openHop's plugin catalogue you'll be able to install it from there with one click instead.)
2. In openHop's dashboard, go to **System > Plugins**, choose **Install wheel** and pick that file. openHop installs it switched off.
3. Create an openHop API token (openHop dashboard > System > API Tokens). Back on the Plugins page, press **Config** in SpamGuard's row, paste the token into `api_key` and press **Save**. Leave the other settings as they are unless you need to change them.
4. Press **Enable** in SpamGuard's row. openHop starts SpamGuard and restarts it if it ever stops unexpectedly. The row shows RUNNING, and **Logs** shows what it's doing.
5. Press the **Open** button in SpamGuard's row (the arrow in a box) to go to SpamGuard's own page, which is on port 8091 of your repeater unless you change `listen_port`. You can also bookmark `http://<your-repeater>:8091/`. Leave it in **Monitor** for a day (it shows what it *would* stop), then switch to **Protect**.

## Settings in openHop's Plugins page

| Setting | What it does |
|---|---|
| `api_key` | Your openHop API token (required) |
| `openhop_url` | Where openHop's web API is. Leave as `http://127.0.0.1:8000`; the plugin runs alongside openHop |
| `mode` | `monitor` or `protect` at first start (you can switch on SpamGuard's page) |
| `sensitivity` | `relaxed`, `balanced` or `strict` at first start |
| `listen_port` | The port for SpamGuard's own page (default 8091) |
| `hashtag_channels` | Extra hashtag channels to protect, e.g. `["#chat", "#test"]` |
| `listen_api_key` | A password for changes on SpamGuard's page. Leave empty for none; anyone on your network can then change settings there |

openHop saves these settings as a whole, so restart the plugin after changing them. Everything else is changed on SpamGuard's own page.

openHop also lists SpamGuard under its web frontends (System > Web Options), because the Open button is a small page openHop serves. SpamGuard isn't a replacement for openHop's dashboard, so if it's picked there by mistake, SpamGuard puts openHop's own dashboard back straight away.

## openHop in Docker or on Unraid

The plugin runs inside openHop's container, so SpamGuard's page on port 8091 is only reachable once that port is published on openHop's container. In openHop's compose file add `- "8091:8091"` under `ports:` and recreate the container. On Unraid, add a port mapping for 8091 to the openHop app.

If you'd rather not change openHop's container, run SpamGuard in its own container instead: see [docker.md](docker.md).

## Updating

SpamGuard's page tells you when a new version is out (Updates in its menu). Press **Update**: SpamGuard fetches the new plugin file, hands it to openHop, and openHop restarts it on the new version. Settings and everything it has learnt are kept. You can also install a newer wheel by hand: download it from the [latest release](https://github.com/flackrat/openhop-spamguard/releases/latest), choose System > Plugins > Install wheel in openHop, then press Disable and Enable on SpamGuard's row so it restarts on the new version. If your plugin is 5.21, update it this way once: 5.21's page sends you to openHop's Plugins page, which has no update button of its own. From 5.22 on, the Update button does it all.

## Plugin manager isn't running

If openHop's System > Plugins page says the plugin manager is unavailable (or SpamGuard's page says so), openHop's plugin manager service isn't running. This can happen after updating an openHop that was installed directly on the Pi. On the Pi:

```
sudo systemctl enable --now openhop-plugin-manager
```

If that says the service doesn't exist, install it from openHop itself and start it:

```
UNIT=$(/opt/openhop_repeater/venv/bin/python -I -c 'from importlib.metadata import distribution; print(distribution("openhop_repeater").locate_file("repeater/plugins/openhop-plugin-manager.service"))')
sudo install -o root -g root -m 0644 "$UNIT" /etc/systemd/system/openhop-plugin-manager.service
sudo systemctl daemon-reload
sudo systemctl enable --now openhop-plugin-manager
```

If it starts and stops again straight away, check that openHop's `config.yaml` doesn't have `enabled: false` under `plugins:`.

## Backups

openHop's own backup doesn't include plugin data. Everything SpamGuard has learnt is in its plugin data folder, `/var/lib/openhop_repeater/plugins/openhop-spamguard/data` on an openHop installed directly on a Pi (inside openHop's data volume in Docker). Copy that folder if you want a backup.

## Don't make SpamGuard openHop's main web page

Plugin versions 5.20 and 5.21 had a page that openHop offers under its web frontend setting, and choosing it would replace openHop's dashboard. From 5.26 that page is SpamGuard's Open button, and if it's ever chosen as openHop's main page SpamGuard puts openHop's dashboard back within a minute. If you're still on 5.20 or 5.21 and it was chosen by mistake: on the Pi, remove the `web_path:` line under `web:` in `/etc/openhop_repeater/config.yaml` and run `sudo systemctl restart openhop-repeater`, then update SpamGuard.

## Going back

To return to the older install after a move: disable the plugin in openHop (System > Plugins), then on the Pi run `sudo systemctl enable --now openhop-spamguard`. The plugin lets go of the repeater as soon as it is disabled, so the old copy takes over straight away.

## Removing it

Uninstalling the plugin stops SpamGuard but leaves its rules in openHop, so blocking would carry on with no one to end it. Before uninstalling, open openHop's policy settings and delete the rules whose names start with `spamguard:` and the `spamguard` object, or switch SpamGuard to **Pause** on its own page and wait a minute so it takes its blocks back out first.

## Differences from the normal install

