#!/bin/sh
# macOS installers have no uninstall: `sudo /usr/local/share/tergite-mss/uninstall.sh`.
# Leaves the account, /usr/local/etc/tergite-mss and /usr/local/var/tergite-mss, which hold
# the only copy of the secrets and possibly the database.

set -e

label=se.chalmersnextlabs.tergite-mss

[ "$(id -u)" = 0 ] || {
	echo "run it with sudo" >&2
	exit 1
}

launchctl bootout "system/$label" 2>/dev/null || true
rm -f "/Library/LaunchDaemons/$label.plist" /usr/local/bin/tergite-mss
rm -rf /usr/local/lib/tergite-mss /usr/local/share/tergite-mss
pkgutil --forget "$label" >/dev/null 2>&1 || true
echo "tergite-mss: removed; its config, data and log are still in /usr/local/etc, /usr/local/var."
