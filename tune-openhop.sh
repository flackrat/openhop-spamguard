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
# 3. Rule-check fix: openHop's rule checker remembers each channel message's decoded sender and
#    text under Python's id() for the packet, and never forgets it until the rules are reloaded.
#    Python reuses ids, so a new packet can be checked with an OLD message's sender and text:
#    spam can be let through as a "known person", or a genuine message dropped. The fix clears
#    that memory at the start of every check (one line). Reported to openHop; an openHop update
#    that contains its own fix makes this unnecessary, and one that doesn't removes it again
#    (SpamGuard's Health panel says so).
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
  echo "openHop's sqlite_handler.py was not found under /opt/openhop_repeater - skipping the speed fix."
  F=/dev/null
fi

current=$(grep -oE "_cumulative_counts_ttl_sec = [0-9.]+" "$F" | awk '{print $3}')
restart=0
PE=$(find /opt/openhop_repeater -path "*repeater/policy_engine.py" 2>/dev/null | head -1)
PY=/opt/openhop_repeater/venv/bin/python; [ -x "$PY" ] || PY=python3
# rule-check fix state: applied | needed | not-needed | unknown
rulefix_state() {
  [ -n "$PE" ] && [ -f "$PE" ] || { echo unknown; return; }
  if grep -q "spamguard-fix: clear decrypt cache" "$PE"; then echo applied
  elif grep -q "_channel_decrypt_cache\[packet_key\]" "$PE" && grep -q "packet_key = id(packet)" "$PE"; then
    if awk '/def evaluate\(/{f=1} f&&/_channel_decrypt_cache.clear\(\)/{print; exit} f&&/for rule in self.rules/{exit}' "$PE" | grep -q clear; then echo not-needed; else echo needed; fi
  else echo not-needed; fi
}
rulefix_apply() {
  [ -f "$PE.spamguard-orig" ] || cp "$PE" "$PE.spamguard-orig"
  "$PY" - "$PE" <<'PYFIX'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
m = re.search(r"(    def evaluate\(self, packet, context[^)]*\)[^:]*:\n(?:.*\n)*?        if not self\.enabled:\n            return [^\n]*\n)", s)
if not m:
    sys.exit(1)
fix = "        self._channel_decrypt_cache.clear()  # spamguard-fix: clear decrypt cache (ids are reused)\n"
s = s[:m.end()] + fix + s[m.end():]
compile(s, p, "exec")
open(p, "w", encoding="utf-8").write(s)
PYFIX
}

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
    case "$(rulefix_state)" in
      applied) echo "Rule-check fix: applied." ;;
      needed) echo "Rule-check fix: NOT applied (blocked spam can sometimes be let through)." ;;
      not-needed) echo "Rule-check fix: not needed for this openHop version." ;;
      *) echo "Rule-check fix: openHop's policy_engine.py not found." ;;
    esac
    exit 0 ;;
  undo)
    undone=0
    if [ "$current" = "60.0" ]; then
      sed -i 's/self._cumulative_counts_ttl_sec = 60.0/self._cumulative_counts_ttl_sec = 3.0/' "$F"
      echo "Speed fix removed."; undone=1
    else
      echo "Speed fix is not applied - nothing to undo."
    fi
    if [ "$(rulefix_state)" = applied ]; then
      sed -i '/spamguard-fix: clear decrypt cache/d' "$PE"
      echo "Rule-check fix removed."; undone=1
    fi
    [ "$undone" = 1 ] && systemctl restart openhop-repeater && echo "openHop restarted."
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

# --- 3. rule-check fix
case "$(rulefix_state)" in
  needed)
    if ask "Apply the openHop rule-check fix (stops blocked spam sometimes being let through as a known person)?"; then
      if rulefix_apply && [ "$(rulefix_state)" = applied ]; then
        echo "Rule-check fix applied (original saved as $PE.spamguard-orig)."; restart=1
      else
        [ -f "$PE.spamguard-orig" ] && cp "$PE.spamguard-orig" "$PE"
        echo "Could not apply the rule-check fix - openHop left unchanged." >&2
      fi
    else
      echo "Rule-check fix skipped."
    fi ;;
  applied) echo "Rule-check fix already applied." ;;
  not-needed) echo "This openHop version doesn't need the rule-check fix." ;;
esac

if [ "$restart" = 1 ]; then
  systemctl restart openhop-repeater && echo "openHop restarted."
fi
