#!/bin/sh
# Gives the service account its directories, saves debconf's answers for provision.sh, then
# enables and starts the service. Never calls a package manager: dpkg holds its lock while
# this runs, which is why the databases are provisioned on the service's start instead.

set -e

service_user=tergite-mss
config=/etc/tergite-mss/mss-config.toml
answers=/etc/tergite-mss/provision.env

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

if [ "$1" = configure ] && [ -e /usr/share/debconf/confmodule ] && [ ! -f "$config" ]; then
	save_answers() {
		for question in database database_url database_password redis redis_url redis_password; do
			db_get "tergite-mss/$question"
			printf '%s=%s\n' "$question" "$RET"
		done
	}
	. /usr/share/debconf/confmodule
	(umask 077 && save_answers >"$answers")
	# the config is the one place a password is kept
	db_set tergite-mss/database_password ""
	db_set tergite-mss/redis_password ""
	db_stop
fi

if [ -f "$config" ] || [ -f "$answers" ]; then
	is_configured=yes
else
	is_configured=no
	echo "tergite-mss: not starting, $config does not exist yet." >&2
fi

if [ -d /run/systemd/system ]; then
	systemctl daemon-reload
	if [ "$is_fresh" = yes ]; then
		systemctl enable tergite-mss.service
	fi
	# without waiting: provisioning retries until a database apt is still installing is up
	if [ "$is_configured" = yes ]; then
		systemctl restart --no-block tergite-mss.service
	fi
elif command -v rc-update >/dev/null 2>&1; then
	if [ "$is_fresh" = yes ]; then
		rc-update add tergite-mss default
	fi
	if [ "$is_configured" = yes ]; then
		rc-service tergite-mss restart ||
			echo "tergite-mss: did not start, see /var/log/messages." >&2
	fi
fi
