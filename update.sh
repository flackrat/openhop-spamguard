#!/usr/bin/env bash
# Updates SpamGuard from its GitHub releases. Nothing is ever installed automatically:
# this runs only when you run it, or when you press "Update" on SpamGuard's page.
#
#   sudo bash /opt/openhop_spamguard/update.sh --check          show installed and latest versions
#   sudo bash /opt/openhop_spamguard/update.sh                  install the latest release
#   sudo bash /opt/openhop_spamguard/update.sh --version v5.8   install a particular release (also to go back)
#
# It downloads the release from GitHub over HTTPS, keeps a copy of the current version,
# installs the new one, and puts the old one back if SpamGuard doesn't start afterwards.
set -uo pipefail

CONF=${SG_CONF:-/etc/openhop_spamguard/config.yaml}
APP=${SG_APP:-/opt/openhop_spamguard}
STATE=${SG_STATE:-/var/lib/openhop_spamguard}
GH_API=${SG_GH_API:-https://api.github.com}
GH_WEB=${SG_GH_WEB:-https://github.com}
STATUS=$STATE/update-status.json
REQUEST=$STATE/update-request
DEFAULT_REPO="flackrat/openhop-spamguard"
PY=/opt/openhop_repeater/venv/bin/python
[ -x "$PY" ] || PY=python3

MODE=install; WANT=""; FROM_REQUEST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --version) WANT="${2:-}"; shift ;;
    --from-request) FROM_REQUEST=1 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }

status() {  # status STATE MESSAGE [FROM] [TO]
  install -d -o repeater -g repeater "$STATE" 2>/dev/null || true
  "$PY" - "$STATUS" "$1" "$2" "${3:-}" "${4:-}" <<'PY'
import json, sys, time, os
path, state, msg, frm, to = sys.argv[1:6]
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump({"state": state, "message": msg, "from": frm, "to": to, "ts": time.time()}, f)
os.replace(tmp, path)
PY
  chown repeater:repeater "$STATUS" 2>/dev/null || true
  echo "$2"
}

if [ "$FROM_REQUEST" = 1 ]; then
  # Asked for from SpamGuard's page. Take the request away first so it can't repeat.
  [ -f "$REQUEST" ] || exit 0
  WANT=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('version',''))" "$REQUEST" 2>/dev/null)
  rm -f "$REQUEST"
fi
if [ -n "$WANT" ] && ! [[ "$WANT" =~ ^v?[0-9]+(\.[0-9]+){1,3}$ ]]; then
  status failed "Not a version number: $WANT"; exit 1
fi

REPO=$(grep -E "^update_repo:" "$CONF" 2>/dev/null | head -1 | sed -E 's/^update_repo:\s*//; s/["'"'"' ]//g')
[ -n "$REPO" ] || REPO="$DEFAULT_REPO"
if ! [[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  status failed "update_repo in $CONF is not in owner/name form"; exit 1
fi

CURRENT=$(grep -oE '^VERSION = "[^"]+"' "$APP/spamguard.py" 2>/dev/null | cut -d'"' -f2)
LATEST=$(curl -fsSL --max-time 20 -H "Accept: application/vnd.github+json" \
           "$GH_API/repos/$REPO/releases/latest" 2>/dev/null \
         | "$PY" -c "import json,sys; print(json.load(sys.stdin).get('tag_name',''))" 2>/dev/null)
if [ -z "$LATEST" ]; then  # no GitHub "release" yet: use the newest version tag
  LATEST=$(curl -fsSL --max-time 20 -H "Accept: application/vnd.github+json" \
             "$GH_API/repos/$REPO/tags?per_page=100" 2>/dev/null | "$PY" -c "
import json, re, sys
tags = [t.get('name', '') for t in json.load(sys.stdin)]
tags = [t for t in tags if re.fullmatch(r'v?\d+(\.\d+){1,3}', t)]
print(max(tags, key=lambda t: tuple(int(x) for x in re.findall(r'\d+', t))) if tags else '')" 2>/dev/null)
fi
if [ -z "$LATEST" ]; then  # API limit reached (60 an hour per internet address): ask the web page instead
  LATEST=$(curl -fsSI --max-time 20 "$GH_WEB/$REPO/releases/latest" 2>/dev/null \
             | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}' | tail -1 | sed -nE 's#.*/releases/tag/(v?[0-9]+(\.[0-9]+){1,3})$#\1#p')
fi

if [ "$MODE" = check ]; then
  echo "Installed: v${CURRENT:-?}"
  echo "Latest:    ${LATEST:-could not reach GitHub} (from github.com/$REPO)"
  exit 0
fi

TAG="${WANT:-$LATEST}"
if [ -z "$TAG" ]; then status failed "Could not reach GitHub to find the latest version."; exit 1; fi
[[ "$TAG" == v* ]] || TAG="v$TAG"
if [ "${TAG#v}" = "$CURRENT" ] && [ -z "$WANT" ]; then
  status done "Already up to date (v$CURRENT)." "$CURRENT" "$CURRENT"; exit 0
fi

status running "Downloading $TAG..." "$CURRENT" "${TAG#v}"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
# The release's own download file first (GitHub counts these, so the author can see roughly
# how many updates are installed; nothing else is sent), then GitHub's automatic archive.
if ! curl -fsSL --max-time 120 -o "$WORK/release.tar.gz" "$GH_WEB/$REPO/releases/download/$TAG/spamguard-$TAG.tar.gz" \
   && ! curl -fsSL --max-time 120 -o "$WORK/release.tar.gz" "$GH_WEB/$REPO/archive/refs/tags/$TAG.tar.gz"; then
  status failed "Download of $TAG failed." "$CURRENT" "${TAG#v}"; exit 1
fi
mkdir "$WORK/src" && tar xzf "$WORK/release.tar.gz" -C "$WORK/src" --strip-components=1 || {
  status failed "The download for $TAG was damaged." "$CURRENT" "${TAG#v}"; exit 1; }
NEWVER=$(grep -oE '^VERSION = "[^"]+"' "$WORK/src/spamguard.py" 2>/dev/null | cut -d'"' -f2)
if [ ! -f "$WORK/src/install.sh" ] || [ "$NEWVER" != "${TAG#v}" ]; then
  status failed "$TAG doesn't look like a SpamGuard release (version inside: ${NEWVER:-none})." "$CURRENT" "${TAG#v}"; exit 1
fi

# Keep the current version so it can be put back.
BACKUP=$STATE/previous-version
rm -rf "$BACKUP"; mkdir -p "$BACKUP"
cp -a "$APP/." "$BACKUP/" 2>/dev/null || true
cp -a /etc/systemd/system/openhop-spamguard.service "$STATE/previous-version.service" 2>/dev/null || true

status running "Installing $TAG..." "$CURRENT" "$NEWVER"
if ! (cd "$WORK/src" && bash install.sh </dev/null >"$STATE/update-install.log" 2>&1); then
  status failed "The installer for $TAG failed (see $STATE/update-install.log). Putting v$CURRENT back." "$CURRENT" "$NEWVER"
  cp -a "$BACKUP/." "$APP/"; systemctl restart openhop-spamguard; exit 1
fi

# Give the new version a moment, then make sure it is running and answering.
for i in $(seq 1 30); do
  sleep 2
  if systemctl is-active --quiet openhop-spamguard && curl -fs --max-time 3 http://127.0.0.1:8091/health >/dev/null 2>&1; then
    status done "Updated from v$CURRENT to v$NEWVER." "$CURRENT" "$NEWVER"; exit 0
  fi
done
# /health answers 503 when it has a warning, so a running service also counts as started.
if systemctl is-active --quiet openhop-spamguard; then
  status done "Updated from v$CURRENT to v$NEWVER." "$CURRENT" "$NEWVER"; exit 0
fi
status failed "v$NEWVER didn't start, so v$CURRENT was put back." "$CURRENT" "$NEWVER"
cp -a "$BACKUP/." "$APP/"
[ -f "$STATE/previous-version.service" ] && cp "$STATE/previous-version.service" /etc/systemd/system/openhop-spamguard.service && systemctl daemon-reload
systemctl restart openhop-spamguard
exit 1
