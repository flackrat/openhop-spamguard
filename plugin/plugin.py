"""Start SpamGuard as an openHop plugin.

openHop's plugin manager runs this with no arguments, in the plugin's data folder, with
OPENHOP_PLUGIN_DATA set. SpamGuard's settings for openHop (API token, address, web page port)
live in that folder's config.json, which openHop's dashboard edits under System > Plugins.
Everything SpamGuard learns is kept in the same folder."""
import json
import os
import sys


def main() -> None:
    data = os.environ.get("OPENHOP_PLUGIN_DATA") or os.getcwd()
    os.environ["SPAMGUARD_PLUGIN"] = "1"
    os.environ.setdefault("SPAMGUARD_DATA", data)
    config = os.path.join(data, "config.json")
    try:  # a small status note openHop's dashboard can show
        with open(config) as f:
            port = int((json.load(f) or {}).get("listen_port") or 8091)
    except (OSError, ValueError, TypeError):
        port = 8091
    try:
        with open(os.path.join(data, "runtime.json"), "w") as f:
            json.dump({"web_page_port": port}, f)
    except OSError:
        pass
    sys.argv = ["openhop-spamguard", "--config", config]
    from openhop_spamguard import spamguard
    spamguard.main()


if __name__ == "__main__":
    main()
