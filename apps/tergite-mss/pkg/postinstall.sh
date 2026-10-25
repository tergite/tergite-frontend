#!/bin/sh
# Gives the service account its directories, then enables the service.
# Never calls a package manager: dpkg holds its lock while this runs.

set -e

service_user=tergite-mss
config=/etc/tergite-mss/mss-config.toml

# deb's `configure` with no old version, rpm's 1, or apk's post-install (its upgrades
# run post-upgrade with the old version too); an upgrade keeps a service disabled
case "$1:$2" in
	configure: | 1: | [0-9]*.*:) is_fresh=yes ;;
	*) is_fresh=no ;;
esac

# the config holds every secret: root's, readable by the service alone
mkdir -p /etc/tergite-mss /var/lib/tergite-mss
chown root:"$service_user" /etc/tergite-mss
chmod 0750 /etc/tergite-mss
chown "$service_user":"$service_user" /var/lib/tergite-mss
chmod 0750 /var/lib/tergite-mss

if [ -d /run/systemd/system ]; then
	systemctl daemon-reload
	if [ "$is_fresh" = yes ]; then
		systemctl enable tergite-mss.service
	fi
	if [ -f "$config" ]; then
		systemctl restart tergite-mss.service
	else
		echo "tergite-mss: not starting, $config does not exist yet."
	fi
elif command -v rc-update >/dev/null 2>&1; then
	if [ "$is_fresh" = yes ]; then
		rc-update add tergite-mss default
	fi
	if [ -f "$config" ]; then
		rc-service tergite-mss restart
	else
		echo "tergite-mss: not starting, $config does not exist yet."
	fi
fi
