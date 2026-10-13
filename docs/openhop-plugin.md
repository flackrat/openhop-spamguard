# SpamGuard as an openHop plugin

openHop has a plugin system (System > Plugins in its dashboard) that works the same whether openHop is installed directly, in Docker, on Unraid or as a Home Assistant add-on. SpamGuard can run as one of those plugins, so you don't need SSH, an installer or a separate container.

Use either the plugin or one of the other installs, not both: two copies of SpamGuard on one repeater would fight over its rules.

## Install

1. Download `openhop_spamguard-<version>-py3-none-any.whl` from the latest [release](https://github.com/flackrat/openhop-spamguard/releases/latest). (Once SpamGuard is in openHop's plugin catalogue you'll be able to install it from there with one click instead.)
2. In openHop's dashboard, go to **System > Plugins**, choose **Install wheel** and pick that file. openHop installs it switched off.
3. Open SpamGuard's settings in the Plugins page and paste an openHop API token into `api_key` (openHop dashboard > System > Configuration > Access > API Tokens). Leave the other settings as they are unless you need to change them.
4. Enable the plugin. openHop starts SpamGuard and restarts it if it ever stops unexpectedly.
5. Open SpamGuard's page from the plugin's page in openHop, or go to `http://<your-repeater>:8091/`. Leave it in **Monitor** for a day (it shows what it *would* stop), then switch to **Protect**.

## Settings in openHop's Plugins page

| Setting | What it does |
|---|---|
| `api_key` | Your openHop API token (required) |
| `openhop_url` | Where openHop's web API is. Leave as `http://127.0.0.1:8000`; the plugin runs alongside openHop |
| `mode` | `monitor` or `protect` at first start (you can switch on SpamGuard's page) |
| `sensitivity` | `relaxed`, `balanced` or `strict` at first start |
| `listen_port` | The port for SpamGuard's own page (default 8091) |
| `hashtag_channels` | Extra hashtag channels to protect, e.g. `["#chat", "#test"]` |

openHop saves these settings as a whole, so restart the plugin after changing them. Everything else is changed on SpamGuard's own page.

## openHop in Docker or on Unraid

The plugin runs inside openHop's container, so SpamGuard's page on port 8091 is only reachable once that port is published on openHop's container. In openHop's compose file add `- "8091:8091"` under `ports:` and recreate the container. On Unraid, add a port mapping for 8091 to the openHop app.

If you'd rather not change openHop's container, run SpamGuard in its own container instead: see [docker.md](docker.md).

## Updating

SpamGuard's page tells you when a new version is out. Install the new release's wheel the same way (System > Plugins > Install wheel); openHop keeps SpamGuard's settings and everything it has learnt. Once SpamGuard is in the catalogue, updates appear there.

## Removing it

Uninstalling the plugin stops SpamGuard but leaves its rules in openHop, so blocking would carry on with no one to end it. Before uninstalling, open openHop's policy settings and delete the rules whose names start with `spamguard:` and the `spamguard` object, or switch SpamGuard to **Pause** on its own page and wait a minute so it takes its blocks back out first.

## Differences from the normal install

- Updates come from openHop's Plugins page, not SpamGuard's Update button.
- The optional openHop speed fix isn't applied automatically; see the main README if your Pi needs it.
