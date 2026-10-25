#!/bin/sh
# Creates the service account before the files land, so /etc/tergite-mss can be its group's

set -e

service_user=tergite-mss

if ! id "$service_user" >/dev/null 2>&1; then
	if command -v useradd >/dev/null 2>&1; then
		useradd --system --home-dir /var/lib/tergite-mss --no-create-home \
			--shell "$(command -v nologin || echo /sbin/nologin)" "$service_user"
	else
		# Alpine's busybox
		addgroup -S "$service_user" 2>/dev/null || true
		adduser -S -D -H -h /var/lib/tergite-mss -s /sbin/nologin \
			-G "$service_user" "$service_user"
	fi
fi
