#!/usr/bin/env bash
# Speeds up openHop's packet saving on small Pis (see README: "openHop running behind").
#
#   sudo bash tune-openhop.sh            apply (asks before each change)
#   sudo bash tune-openhop.sh --yes      apply without asking
#   sudo bash tune-openhop.sh --check    only report
#   sudo bash tune-openhop.sh --undo     put openHop's original value back
#
# 1. openHop recounts every stored packet each time it saves one, keeping the answer for only
#    3 seconds. The answer is only used for the graphs, which are written once a minute, so
#    keeping it for 60 seconds changes nothing you can see and removes most of the work.
#    An openHop upgrade puts the old value back; SpamGuard's Health panel says so, and you
#    just run this script again.
# 2. Optionally keep 7 days of packet history instead of 31, so the database stays small.
set -uo pipefail

MODE=apply; YES=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --check) MODE=check ;;
    --undo) MODE=undo ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }

ask() {  # ask "question" -> 0 for yes
  [ "$YES" = 1 ] && return 0
  [ -t 0 ] || return 1
  read -r -p "$1 [y/N] " r; [[ "$r" =~ ^[Yy] ]]
}

CONF=/etc/openhop_repeater/config.yaml
F=$(find /opt/openhop_repeater -path "*repeater/data_acquisition/sqlite_handler.py" 2>/dev/null | head -1)
if [ -z "$F" ]; then
  echo "openHop's sqlite_handler.py was not found under /opt/openhop_repeater - nothing to do."
  exit 0
fi

current=$(grep -oE "_cumulative_counts_ttl_sec = [0-9.]+" "$F" | awk '{print $3}')
restart=0

case "$MODE" in
  check)
    if [ -z "$current" ]; then echo "Speed fix: not applicable to this openHop version."
    elif [ "$current" = "3.0" ]; then echo "Speed fix: NOT applied (openHop keeps its packet count for 3 s)."
    else echo "Speed fix: applied (count kept for ${current} s)."; fi
    if [ -f "$CONF" ]; then
      days=$(grep -E "^\s*sqlite_cleanup_days:" "$CONF" | head -1 | awk '{print $2}')
      echo "Packet history kept: ${days:-31 (default)} days"
    fi
    ls -lh /var/lib/openhop_repeater/repeater.db 2>/dev/null | awk '{print "Database size: "$5}'
    exit 0 ;;
  undo)
    if [ "$current" = "60.0" ]; then
      sed -i 's/self._cumulative_counts_ttl_sec = 60.0/self._cumulative_counts_ttl_sec = 3.0/' "$F"
      echo "Speed fix removed."; systemctl restart openhop-repeater && echo "openHop restarted."
    else
      echo "Speed fix is not applied - nothing to undo."
    fi
    exit 0 ;;
esac

# --- 1. counting fix
if [ -z "$current" ]; then
  echo "This openHop version doesn't have the 3-second packet count - no speed fix needed."
elif [ "$current" = "3.0" ]; then
  if ask "Apply the openHop speed fix (keep its packet count for 60 s instead of 3 s)?"; then
    [ -f "$F.spamguard-orig" ] || cp "$F" "$F.spamguard-orig"
    sed -i 's/self._cumulative_counts_ttl_sec = 3.0/self._cumulative_counts_ttl_sec = 60.0/' "$F"
    if grep -q "_cumulative_counts_ttl_sec = 60.0" "$F"; then
      echo "Speed fix applied."; restart=1
    else
      echo "Could not apply the speed fix - openHop left unchanged." >&2
    fi
  else
    echo "Speed fix skipped."
  fi
else
  echo "Speed fix already applied (count kept for ${current} s)."
fi

# --- 2. history kept
if [ -f "$CONF" ]; then
  days=$(grep -E "^\s*sqlite_cleanup_days:" "$CONF" | head -1 | awk '{print $2}')
  if [ -n "$days" ] && [ "$days" -gt 7 ] 2>/dev/null; then
    if ask "openHop keeps $days days of packet history. Keep 7 days instead (smaller, faster database; graphs are not affected)?"; then
      cp "$CONF" "$CONF.spamguard-bak"
      sed -i -E "s/^(\s*sqlite_cleanup_days:)\s*[0-9]+/\1 7/" "$CONF"
      echo "Packet history set to 7 days (old config saved as $CONF.spamguard-bak)."; restart=1
    fi
  elif [ -z "$days" ]; then
    echo "No sqlite_cleanup_days line in $CONF (openHop's default is 31 days). Add it under storage > retention to change it."
  fi
fi

if [ "$restart" = 1 ]; then
  systemctl restart openhop-repeater && echo "openHop restarted."
fi
