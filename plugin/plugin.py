"""Start SpamGuard as an openHop plugin.

openHop's plugin manager runs this with no arguments, in the plugin's data folder, with
OPENHOP_PLUGIN_DATA set. SpamGuard's settings for openHop (API token, address, web page port)
live in that folder's config.json, which openHop's dashboard edits under System > Plugins.
SpamGuard's own page is on its own port (8091 by default), not inside openHop's dashboard.
Everything SpamGuard learns is kept in the same folder."""
import json
import os
import sys


def take_over(data: str, config: str) -> None:
    """When SpamGuard is being moved here from a normal install (or Docker), the settings include a
    one-time link to that copy. Fetch everything it has learnt before starting, then forget the link."""
    try:
        with open(config) as f:
            cfg = json.load(f) or {}
    except (OSError, ValueError):
        return
    src = cfg.get("import_from") if isinstance(cfg, dict) else None
    if not src:
        return
    import time
    import urllib.request
    for _ in range(20):
        try:
            with urllib.request.urlopen(src, timeout=20) as r:
                state = json.loads(r.read().decode())
            if isinstance(state, dict) and "blocks" in state:
                for name, body in (("state.json", state), ("imported.json", {"from": src.split("/handover")[0],
                                                                              "at": time.time()})):
                    tmp = os.path.join(data, name + ".tmp")
                    with open(tmp, "w") as f:
                        json.dump(body, f)
                    os.replace(tmp, os.path.join(data, name))
                print("SpamGuard: picked up everything the previous SpamGuard had learnt", flush=True)
                break
        except Exception as e:  # the other copy may still be starting up
            print(f"SpamGuard: waiting to pick up the previous SpamGuard's data ({e})", flush=True)
            time.sleep(3)
    cfg.pop("import_from", None)
    try:
        tmp = config + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, config)
    except OSError:
        pass


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
    take_over(data, config)
    sys.argv = ["openhop-spamguard", "--config", config]
    from openhop_spamguard import spamguard
    spamguard.main()


if __name__ == "__main__":
    main()
