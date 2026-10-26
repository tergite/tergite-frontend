#!/bin/sh
# Migrates a fresh SQLite database with a built or installed binary, which needs its bundled
# Alembic files: from the repository root, `pkg/smoke-test.sh /usr/bin/tergite-mss`

set -e

binary=$1
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

awk -v url="url = \"sqlite+aiosqlite:///$dir/mss.sqlite\"" '
	/^\[database\]/ { is_database = 1 }
	is_database && /^url/ { print url; is_database = 0; next }
	{ print }
' tests/fixtures/config.test.toml >"$dir/mss-config.toml"

MSS_CONFIG_FILE="$dir/mss-config.toml" PRIVATE_KEY_FILE="$PWD/tests/fixtures/mss_private_key.pem" \
	"$binary" migrate
