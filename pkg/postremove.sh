#!/bin/sh
# Forgets the unit. The account, /etc/tergite-mss and /var/lib/tergite-mss stay, even on
# purge: they hold the only copy of the secrets and possibly the database.

set -e

if [ -d /run/systemd/system ]; then
	systemctl daemon-reload || true
fi

if [ "$1" = purge ] && [ -e /usr/share/debconf/confmodule ]; then
	. /usr/share/debconf/confmodule
	db_purge
fi
