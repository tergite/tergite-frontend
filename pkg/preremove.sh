#!/bin/sh
# Stops the service before its binary goes. The config, its secrets and the data stay.

set -e

# deb's `upgrade` and rpm's 1 are an upgrade, which postinstall restarts the service after
case "$1" in
	upgrade | 1) exit 0 ;;
esac

if [ -d /run/systemd/system ]; then
	systemctl stop tergite-mss.service || true
	systemctl disable tergite-mss.service || true
elif command -v rc-service >/dev/null 2>&1; then
	rc-service tergite-mss stop || true
	rc-update del tergite-mss default || true
fi
