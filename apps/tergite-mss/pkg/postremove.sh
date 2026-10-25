#!/bin/sh
# Forgets the unit. The account, /etc/tergite-mss and /var/lib/tergite-mss stay, even on
# purge: they hold the only copy of the secrets and possibly the database.

set -e

if [ -d /run/systemd/system ]; then
	systemctl daemon-reload || true
fi
