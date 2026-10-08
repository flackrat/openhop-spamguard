#!/usr/bin/env bash
# Removes SpamGuard completely and takes its blocking rules back out of openHop.
#
#   sudo bash /opt/openhop_spamguard/uninstall.sh                     remove SpamGuard
#   sudo bash /opt/openhop_spamguard/uninstall.sh --keep-evidence     keep the evidence log files
#   sudo bash /opt/openhop_spamguard/uninstall.sh --undo-speed-fix    also put openHop's original packet-count setting back
#
# openHop itself, your own openHop rules and openHop's settings are left alone.
set -uo pipefail

KEEP_EVIDENCE=0; UNDO_FIX=0
for a in "$@"; do
  case "$a" in
    --keep-evidence) KEEP_EVIDENCE=1 ;;
    --undo-speed-fix) UNDO_FIX=1 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "Run the uninstaller with sudo: sudo bash $0" >&2; exit 1; }

CONF=/etc/openhop_spamguard/config.yaml
APP=/opt/openhop_spamguard
STATE=/var/lib/openhop_spamguard
PY=/opt/openhop_repeater/venv/bin/python
[ -x "$PY" ] || PY=python3

echo "Stopping SpamGuard..."
systemctl disable --now openhop-spamguard-update.path openhop-spamguard.service >/dev/null 2>&1 || true
systemctl stop openhop-spamguard-update.service >/dev/null 2>&1 || true

# --- take SpamGuard's rules (names starting "spamguard:") out of openHop, keeping everything else
echo "Removing SpamGuard's rules from openHop..."
if [ -f "$CONF" ] && "$PY" - "$CONF" <<'PY'
import json, sys, urllib.request
try:
    import yaml
    cfg = yaml.safe_load(open(sys.argv[1])) or {}
except Exception:
    cfg = {}
url = str(cfg.get("openhop_url") or "http://127.0.0.1:8000").rstrip("/") + "/api/policy"
key = cfg.get("api_key") or ""

def call(method, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-API-Key", key)
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read().decode() or "{}")
    if isinstance(res, dict) and res.get("success") is False:
        raise RuntimeError(res.get("error") or res.get("message") or "API error")
    return res

try:
    res = call("GET")
    pe = dict((res.get("data", res) or {}).get("policy_engine") or {})
    rules = [r for r in (pe.get("rules") or []) if isinstance(r, dict)]
    keep = [r for r in rules if not str(r.get("name", "")).startswith("spamguard:")]
    removed = len(rules) - len(keep)
    objects = pe.get("objects") if isinstance(pe.get("objects"), dict) else {}
    had_list = objects.pop("spamguard", None) is not None  # SpamGuard's list of known names
    if removed or had_list:
        pe["rules"] = keep
        pe["objects"] = objects
        call("POST", {"policy_engine": pe})
    print(f"  Removed {removed} SpamGuard rule(s); {len(keep)} of your own rule(s) left in place.")
except Exception as e:
    print(f"  Could not update openHop's rules ({e}).", file=sys.stderr)
    sys.exit(1)
PY
then :
else
  echo "  SpamGuard's rules may still be in openHop. Remove any rule whose name starts with"
  echo "  \"spamguard:\" in the openHop dashboard, or in /etc/openhop_repeater/policy.yaml, then"
  echo "  restart openHop: sudo systemctl restart openhop-repeater"
fi

# --- openHop speed fix: kept unless asked, because it only makes openHop faster
if [ "$UNDO_FIX" = 1 ] && [ -f "$APP/tune-openhop.sh" ]; then
  bash "$APP/tune-openhop.sh" --undo
fi

echo "Removing SpamGuard's files..."
rm -f /etc/systemd/system/openhop-spamguard.service \
      /etc/systemd/system/openhop-spamguard-update.path \
      /etc/systemd/system/openhop-spamguard-update.service
systemctl daemon-reload
systemctl reset-failed openhop-spamguard openhop-spamguard-update >/dev/null 2>&1 || true
rm -rf /etc/openhop_spamguard
if [ "$KEEP_EVIDENCE" = 1 ] && [ -d "$STATE/evidence" ]; then
  find "$STATE" -mindepth 1 -maxdepth 1 ! -name evidence -exec rm -rf {} +
  echo "  Evidence log kept in $STATE/evidence"
else
  rm -rf "$STATE"
fi
rm -rf "$APP"   # last, as this script lives here

echo
echo "SpamGuard has been removed. openHop, its settings and your own rules are unchanged."
[ "$UNDO_FIX" = 1 ] || echo "The openHop speed fix was left in place (undo it with: sudo bash tune-openhop.sh --undo from the SpamGuard download)."
if grep -qE "^\s*sqlite_cleanup_days:\s*7\b" /etc/openhop_repeater/config.yaml 2>/dev/null; then
  echo "openHop still keeps 7 days of packet history. To go back to its default, set sqlite_cleanup_days to 31"
  echo "in /etc/openhop_repeater/config.yaml and restart openHop."
fi
