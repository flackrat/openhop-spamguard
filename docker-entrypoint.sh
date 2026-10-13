#!/bin/sh
# Make sure the data folder belongs to SpamGuard's own user (Docker creates bind mounts as root),
# then run SpamGuard as that user, never as root.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data
  chown -R spamguard /data 2>/dev/null || true
  exec setpriv --reuid=spamguard --regid="$(id -g spamguard)" --init-groups "$@"
fi
exec "$@"
