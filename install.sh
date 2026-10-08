#!/usr/bin/env bash
# Installs openHop SpamGuard next to a native openHop Repeater install.
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(id -u)" != 0 ]; then
  echo "Run the installer with sudo:  sudo bash install.sh" >&2
  exit 1
fi
if [ "$(ps -p 1 -o comm= 2>/dev/null)" != "systemd" ] || ! command -v systemctl >/dev/null; then
  echo "SpamGuard needs systemd to run as a service (Raspberry Pi OS, Debian and Ubuntu all have it)." >&2
  echo "It can't be installed inside a Docker container or on a system without systemd." >&2
  exit 1
fi
if [ ! -x /opt/openhop_repeater/venv/bin/python ]; then
  echo "openHop wasn't found at /opt/openhop_repeater." >&2
  echo "SpamGuard needs openHop installed natively with its own installer (manage.sh install), not with Docker." >&2
  echo "See docs/openhop-fresh-install.md" >&2
  exit 1
fi
if ! id repeater >/dev/null 2>&1; then
  echo "openHop's service user 'repeater' doesn't exist - is openHop installed with its own installer?" >&2
  exit 1
fi
if ! command -v curl >/dev/null; then
  echo "Note: curl isn't installed, so the Update button won't work. Install it with: sudo apt install curl"
fi

/opt/openhop_repeater/venv/bin/python -c "import Crypto, yaml" \
  || { echo "pycryptodome/PyYAML missing from openHop's venv" >&2; exit 1; }

install -d /opt/openhop_spamguard /etc/openhop_spamguard
install -m 0755 spamguard.py /opt/openhop_spamguard/spamguard.py
install -m 0644 ui.html /opt/openhop_spamguard/ui.html
install -m 0755 replay.py /opt/openhop_spamguard/replay.py
install -m 0755 tune-openhop.sh /opt/openhop_spamguard/tune-openhop.sh
install -m 0755 update.sh /opt/openhop_spamguard/update.sh
install -m 0755 uninstall.sh /opt/openhop_spamguard/uninstall.sh

if [ ! -f /etc/openhop_spamguard/config.yaml ]; then
  install -m 0640 -o root -g repeater config.yaml /etc/openhop_spamguard/config.yaml
  echo "Created /etc/openhop_spamguard/config.yaml"
elif ! grep -q "^sensitivity:" /etc/openhop_spamguard/config.yaml; then
  # Upgrading from v4 or earlier: carry over the token, mode and web settings,
  # then switch to the new, simpler config file.
  cp /etc/openhop_spamguard/config.yaml /etc/openhop_spamguard/config.yaml.old
  /opt/openhop_repeater/venv/bin/python - << 'PY'
import yaml, re
old = yaml.safe_load(open("/etc/openhop_spamguard/config.yaml.old")) or {}
text = open("config.yaml").read()
def put(key, value):
    global text
    text = re.sub(rf'^{key}:.*$', f'{key}: {value}', text, count=1, flags=re.M)
if old.get("api_key"):
    put("api_key", '"%s"' % old["api_key"])
mode = old.get("mode") or ("protect" if old.get("action") == "drop" else "monitor")
put("mode", mode)
for k in ("openhop_url", "listen_api_key"):
    if old.get(k) is not None:
        put(k, '"%s"' % old[k])
if old.get("listen_port"):
    put("listen_port", old["listen_port"])
open("/etc/openhop_spamguard/config.yaml", "w").write(text)
PY
  chown root:repeater /etc/openhop_spamguard/config.yaml
  chmod 0640 /etc/openhop_spamguard/config.yaml
  echo "Upgraded your config to the new format (old one saved as config.yaml.old)"
else
  echo "Keeping existing /etc/openhop_spamguard/config.yaml"
fi

# Offer the openHop speed fix (asks first; skipped when not run from a terminal).
echo
bash /opt/openhop_spamguard/tune-openhop.sh || true
echo

install -m 0644 openhop-spamguard.service /etc/systemd/system/openhop-spamguard.service
# "Update" button on the web page: SpamGuard drops a request file, this root-owned
# service carries it out. Nothing updates unless you ask.
install -m 0644 openhop-spamguard-update.path /etc/systemd/system/openhop-spamguard-update.path
install -m 0644 openhop-spamguard-update.service /etc/systemd/system/openhop-spamguard-update.service
systemctl daemon-reload
systemctl enable openhop-spamguard >/dev/null
systemctl enable --now openhop-spamguard-update.path >/dev/null 2>&1 || true

if grep -q PASTE_OPENHOP_API_TOKEN_HERE /etc/openhop_spamguard/config.yaml; then
  echo
  echo "Next: put your openHop API token in the config, then start it:"
  echo "  sudo nano /etc/openhop_spamguard/config.yaml"
  echo "  sudo systemctl start openhop-spamguard"
else
  systemctl restart openhop-spamguard
  echo "SpamGuard (re)started."
fi
echo "Status page: http://$(hostname -I | awk '{print $1}'):8091/"
