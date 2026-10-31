#!/bin/sh
# Writes /etc/tergite-mss/mss-config.toml and the private key beside it, creating MSS's
# account on a local PostgreSQL or MongoDB. Runs as root before the service's first start,
# when the database apt installed alongside is up, and by hand on rpm or apk.
#
# Reads the answers debconf saved to /etc/tergite-mss/provision.env, one key=value a line:
# database=postgresql|mongodb|url, database_url, database_password. A URL comes without its
# password. No file means a local PostgreSQL.
# Leaves an existing config alone: delete it to provision again.

set -e

dir=/etc/tergite-mss
config=$dir/mss-config.toml
answers=$dir/provision.env
service_user=tergite-mss

main() {
	[ -f "$config" ] && exit 0
	cd /

	database=postgresql
	database_url=
	database_password=
	if [ -f "$answers" ]; then
		while IFS='=' read -r key value; do
			case $key in
				database) database=$value ;;
				database_url) database_url=$value ;;
				database_password) database_password=$value ;;
			esac
		done <"$answers"
	fi

	case $database in
		postgresql)
			password=$(get_secret)
			create_postgresql_user "$password"
			database_url="postgresql+asyncpg://tergite_mss:$password@localhost:5432/tergite_mss"
			;;
		mongodb)
			password=$(get_secret)
			create_mongodb_user "$password"
			database_url="mongodb://tergite-mss:$password@localhost:27017/tergite-mss"
			;;
		url) database_url=$(add_password "$database_url" "$database_password") ;;
		*) fail "unknown database '$database' in $answers" ;;
	esac

	umask 027
	key_password=$(get_secret)
	openssl genpkey -quiet -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -aes-256-cbc \
		-pass "pass:$key_password" -out "$dir/private-mss-key.pem"
	openssl rsa -pubout -passin "pass:$key_password" \
		-in "$dir/private-mss-key.pem" -out "$dir/public-mss-key.pem" 2>/dev/null
	# genpkey writes 0600 whatever the umask, which the service, in the group, could not read
	chmod 0640 "$dir/private-mss-key.pem"

	# written last and whole: its existence is what says provisioning finished
	cat >"$config.new" <<-EOF
		# Written by /usr/share/tergite-mss/provision.sh. Every other setting, and what it
		# does, is in /usr/share/tergite-mss/mss-config.example.toml.

		# the BCCs MSS sends jobs to; each needs public-mss-key.pem from this folder
		backends = []

		[general]
		environment = "production"
		private_key_password = "$key_password"

		[database]
		name = "tergite-mss"
		url = "$database_url"

		[auth]
		jwt_secret = "$(get_secret)"
	EOF
	chgrp "$service_user" "$dir/private-mss-key.pem" "$dir/public-mss-key.pem" "$config.new"
	mv "$config.new" "$config"
	rm -f "$answers"
	echo "tergite-mss: wrote $config"
}

create_postgresql_user() {
	command -v psql >/dev/null 2>&1 ||
		fail "PostgreSQL is not installed: install it, or answer 'existing database' to dpkg-reconfigure tergite-mss"
	as_postgres <<-EOF
		DO \$\$BEGIN
		  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'tergite_mss') THEN
		    ALTER ROLE tergite_mss LOGIN PASSWORD '$1';
		  ELSE
		    CREATE ROLE tergite_mss LOGIN PASSWORD '$1';
		  END IF;
		END\$\$;
	EOF
	if [ -z "$(echo "SELECT 1 FROM pg_database WHERE datname = 'tergite_mss'" | as_postgres)" ]; then
		echo 'CREATE DATABASE tergite_mss OWNER tergite_mss' | as_postgres
	fi
}

create_mongodb_user() {
	command -v mongosh >/dev/null 2>&1 ||
		fail "mongosh is not installed: install MongoDB, or answer 'existing database' to dpkg-reconfigure tergite-mss"
	# dbAdmin for bypassDocumentValidation, which the MongoDB migrations need
	mongosh --quiet mongodb://localhost:27017/tergite-mss --eval "
		const roles = ['readWrite', 'dbAdmin'];
		if (db.getUser('tergite-mss')) db.updateUser('tergite-mss', {pwd: '$1', roles});
		else db.createUser({user: 'tergite-mss', pwd: '$1', roles});
	" >/dev/null ||
		fail "could not create the MongoDB user; with authorization on, create 'tergite-mss' by hand and answer 'existing database'"
}

as_postgres() {
	su -s /bin/sh postgres -c "psql -v ON_ERROR_STOP=1 -qtAX"
}

add_password() {
	case $1 in
		*'"'* | *'\'*) fail "the URL '$1' has a quote or backslash" ;;
	esac
	if [ -z "$2" ]; then
		printf '%s' "$1"
		return
	fi
	scheme=${1%%://*}
	rest=${1#*://}
	case $rest in
		*@*) user=${rest%%@*} host=${rest#*@} ;;
		*) user= host=$rest ;;
	esac
	printf '%s://%s:%s@%s' "$scheme" "$user" "$(encode_url "$2")" "$host"
}

encode_url() {
	printf '%s' "$1" | od -An -tx1 -v | tr -d ' \n' | sed 's/../%&/g'
}

get_secret() {
	od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
}

fail() {
	echo "tergite-mss: $1" >&2
	exit 1
}

main "$@"
