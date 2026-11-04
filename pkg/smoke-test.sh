#!/bin/sh
# Migrates a fresh SQLite database with a built or installed MSS, which needs its bundled
# Alembic files, then serves it a minute at most, failing unless it answers /health and serves
# the dashboard's index.html at /ui/: from the repository root,
# `pkg/smoke-test.sh /usr/bin/tergite-mss`

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

log=$dir/serve.log
MSS_CONFIG_FILE="$dir/mss-config.toml" PRIVATE_KEY_FILE="$PWD/tests/fixtures/mss_private_key.pem" \
	"$binary" serve --host 127.0.0.1 --port 8102 >"$log" 2>&1 &
mss=$!
trap 'kill "$mss" 2>/dev/null; rm -rf "$dir"' EXIT
# quietly, as it fails to connect until MSS listens
if ! curl -fs --retry 60 --retry-delay 1 --retry-connrefused -o /dev/null \
	http://127.0.0.1:8102/health; then
	cat "$log" >&2
	echo "MSS did not answer /health within a minute" >&2
	exit 1
fi
if ! curl -fsS http://127.0.0.1:8102/ui/ | grep -qi "<!doctype html"; then
	cat "$log" >&2
	echo "MSS serves no dashboard at /ui/" >&2
	exit 1
fi
