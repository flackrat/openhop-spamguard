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
# Root's own working files (install log, copy of the current version) live in a folder only root can write,
# never in SpamGuard's state folder, which the service user owns.
ROOTSTATE=${SG_ROOT_STATE:-/var/lib/openhop_spamguard-update}
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

install -d -m 0755 -o root -g root "$ROOTSTATE" 2>/dev/null || mkdir -p "$ROOTSTATE"
LOG=$ROOTSTATE/update-install.log
status() {  # status STATE MESSAGE [FROM] [TO] [PERCENT]
  install -d -o repeater -g repeater "$STATE" 2>/dev/null || true
  "$PY" - "$STATUS" "$1" "$2" "${3:-}" "${4:-}" "${5:-}" "$LOG" <<'PY'
import json, sys, time, os, re
path, state, msg, frm, to, pct, log = sys.argv[1:8]
out = {"state": state, "message": msg, "from": frm, "to": to, "ts": time.time()}
if pct.isdigit():
    out["pct"] = min(int(pct), 100)
# The last two lines the installer printed, cleaned, so the page can show what it is doing.
lines = []
try:
    if state in ("running", "failed") and os.path.exists(log):
        with open(log, errors="replace") as f:
            for raw in f.read().splitlines()[-40:]:
                t = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", raw)
                t = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]+", " ", t)).strip()[:140]
                if t:
                    lines.append(t)
except OSError:
    pass
if lines:
    out["lines"] = lines[-2:]
# Written into a folder the service user owns, so never follow a link planted there: a new file of our own,
# then an atomic rename over the old one (a rename replaces a link, it doesn't write through it).
tmp = path + ".tmp"
try:
    os.unlink(tmp)
except FileNotFoundError:
    pass
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
with os.fdopen(fd, "w") as f:
    json.dump(out, f)
os.replace(tmp, path)
PY
  echo "$2"
}

if [ "$FROM_REQUEST" = 1 ]; then
  # Asked for from SpamGuard's page. Take the request away first so it can't repeat.
  [ -f "$REQUEST" ] || exit 0
  ACTION=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('action','update'))" "$REQUEST" 2>/dev/null)
  WANT=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('version',''))" "$REQUEST" 2>/dev/null)
  rm -f "$REQUEST"
  if [ "$ACTION" = "retire" ]; then
    # SpamGuard has moved into openHop as a plugin: switch this copy off but keep its files, so it can
    # be switched back on (sudo systemctl enable --now openhop-spamguard) if ever needed.
    status done "Moved to the openHop plugin; this copy is switched off."
    systemctl disable --now openhop-spamguard >/dev/null 2>&1 || true
    exit 0
  fi
  if [ "$ACTION" = "openhop-fix" ]; then
    # Re-apply the openHop rule-check fix (an openHop update removes it). Nothing else changes.
    if out=$(bash "$APP/tune-openhop.sh" --rulefix 2>&1); then
      status done "openHop rule-check fix: $(echo "$out" | head -1)"
    else
      status failed "openHop rule-check fix couldn't be applied: $(echo "$out" | tail -1)"
    fi
    exit 0
  fi
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

rm -f "$LOG"
status running "Downloading $TAG..." "$CURRENT" "${TAG#v}" 5
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
# The release's own download file, checked against the checksums published with the release. Releases from
# 6.28.0 on must pass that check; older ones were published without checksums, so they can still be installed
# (to go back a version) but are marked as unchecked. GitHub's automatic archive is only used for those.
LEGACY=0
[ "$(printf '%s\n%s\n' "${TAG#v}" 6.28.0 | sort -V | head -1)" != "6.28.0" ] && LEGACY=1
CHECKED=0
if ! curl -fsSL --max-time 120 -o "$WORK/release.tar.gz" "$GH_WEB/$REPO/releases/download/$TAG/spamguard-$TAG.tar.gz"; then
  if [ "$LEGACY" = 1 ] && curl -fsSL --max-time 120 -o "$WORK/release.tar.gz" "$GH_WEB/$REPO/archive/refs/tags/$TAG.tar.gz"; then
    echo "Note: $TAG was installed from GitHub's automatic archive, which has no checksum to check." >> "$LOG"
  else
    status failed "Download of $TAG failed." "$CURRENT" "${TAG#v}"; exit 1
  fi
elif curl -fsSL --max-time 30 -o "$WORK/SHA256SUMS" "$GH_WEB/$REPO/releases/download/$TAG/SHA256SUMS"; then
  WANT_SUM=$(awk -v f="spamguard-$TAG.tar.gz" '($2==f || $2=="*" f) && $1 ~ /^[0-9a-fA-F]{64}$/ {print tolower($1); exit}' "$WORK/SHA256SUMS")
  HAVE_SUM=$(sha256sum "$WORK/release.tar.gz" | cut -d' ' -f1)
  if [ -z "$WANT_SUM" ] || [ "$WANT_SUM" != "$HAVE_SUM" ]; then
    status failed "The download for $TAG does not match the checksum published with the release, so nothing was installed." "$CURRENT" "${TAG#v}"; exit 1
  fi
  CHECKED=1
  # If cosign is installed, also check the checksum file's Sigstore signature (it must come from this repository's release workflow).
  if command -v cosign >/dev/null 2>&1 && curl -fsSL --max-time 30 -o "$WORK/SHA256SUMS.sigstore.json" "$GH_WEB/$REPO/releases/download/$TAG/SHA256SUMS.sigstore.json"; then
    if ! cosign verify-blob --bundle "$WORK/SHA256SUMS.sigstore.json" \
         --certificate-identity-regexp "^https://github.com/$REPO/\.github/workflows/release\.yml@" \
         --certificate-oidc-issuer https://token.actions.githubusercontent.com "$WORK/SHA256SUMS" >>"$LOG" 2>&1; then
      status failed "The signature on $TAG's checksums did not verify, so nothing was installed." "$CURRENT" "${TAG#v}"; exit 1
    fi
    CHECKED=2
  fi
elif [ "$LEGACY" = 0 ]; then
  status failed "$TAG was published without checksums, so it can't be checked and nothing was installed." "$CURRENT" "${TAG#v}"; exit 1
else
  echo "Note: $TAG was published before checksums existed, so the download could not be checked." >> "$LOG"
fi
mkdir "$WORK/src" && tar xzf "$WORK/release.tar.gz" -C "$WORK/src" --strip-components=1 || {
  status failed "The download for $TAG was damaged." "$CURRENT" "${TAG#v}"; exit 1; }
NEWVER=$(grep -oE '^VERSION = "[^"]+"' "$WORK/src/spamguard.py" 2>/dev/null | cut -d'"' -f2)
if [ ! -f "$WORK/src/install.sh" ] || [ "$NEWVER" != "${TAG#v}" ]; then
  status failed "$TAG doesn't look like a SpamGuard release (version inside: ${NEWVER:-none})." "$CURRENT" "${TAG#v}"; exit 1
fi

# Keep the current version so it can be put back.
BACKUP=$ROOTSTATE/previous-version
rm -rf "$BACKUP"; mkdir -p "$BACKUP"
cp -a "$APP/." "$BACKUP/" 2>/dev/null || true
cp -a /etc/systemd/system/openhop-spamguard.service "$STATE/previous-version.service" 2>/dev/null || true

status running "Installing $TAG$([ "$CHECKED" -ge 1 ] && echo " (checksum OK$([ "$CHECKED" = 2 ] && echo ', signature OK'))" )..." "$CURRENT" "$NEWVER" 30
(cd "$WORK/src" && exec bash install.sh </dev/null >"$LOG" 2>&1) &
IPID=$!
while kill -0 "$IPID" 2>/dev/null; do
  # A guide, not a measurement: the installer doesn't say how many steps it has. Creeps up with its output.
  n=$(wc -l < "$LOG" 2>/dev/null || echo 0); p=$((30 + n / 2)); [ "$p" -gt 85 ] && p=85
  status running "Installing $TAG..." "$CURRENT" "$NEWVER" "$p" >/dev/null
  sleep 3
done
if ! wait "$IPID"; then
  status failed "The installer for $TAG failed (see $STATE/update-install.log). Putting v$CURRENT back." "$CURRENT" "$NEWVER"
  cp -a "$BACKUP/." "$APP/"; systemctl restart openhop-spamguard; exit 1
fi

# Give the new version a moment, then make sure it is running and answering.
for i in $(seq 1 30); do
  status running "Starting v$NEWVER..." "$CURRENT" "$NEWVER" $((88 + i / 5)) >/dev/null
  sleep 2
  if systemctl is-active --quiet openhop-spamguard && curl -fs --max-time 3 http://127.0.0.1:8091/health >/dev/null 2>&1; then
    status done "Updated from v$CURRENT to v$NEWVER." "$CURRENT" "$NEWVER" 100; exit 0
  fi
done
# /health answers 503 when it has a warning, so a running service also counts as started.
if systemctl is-active --quiet openhop-spamguard; then
  status done "Updated from v$CURRENT to v$NEWVER." "$CURRENT" "$NEWVER" 100; exit 0
fi
status failed "v$NEWVER didn't start, so v$CURRENT was put back." "$CURRENT" "$NEWVER"
cp -a "$BACKUP/." "$APP/"
[ -f "$STATE/previous-version.service" ] && cp "$STATE/previous-version.service" /etc/systemd/system/openhop-spamguard.service && systemctl daemon-reload
systemctl restart openhop-spamguard
exit 1
