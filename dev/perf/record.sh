#!/bin/bash
# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Records the performance measures into <out-dir>: Lighthouse on the
# dashboard as MSS serves it, then Locust on MSS from this working tree, with a MongoDB and
# a Redis of its own, all running natively, both over the e2e fixtures. It samples the CPU and
# memory of the MSS, mongod and redis-server processes, and each database's connections.
#
# Usage
# =====
#
#   ./dev/perf/record.sh dev/perf/baselines           # the baseline
#   ./dev/perf/record.sh /tmp/perf                    # a run to compare with it
#   ./dev/perf/record.sh /tmp/perf mss                # MSS alone, or dashboard alone
#   python3 dev/perf/compare.py dev/perf/baselines /tmp/perf
#
# Needs node, uv, mongod, mongosh, redis-server and redis-cli, and ports 8002, 27019 and 6381
# free: MSS takes 8002, where the dashboard's test build calls it; the locustfile reaches
# MongoDB at 27019.
# Compare only runs made on the same machine: the numbers are this machine's.

set -e

LOCUST_VERSION="2.46.7"
LHCI_VERSION="0.15.1"
LOAD_USERS=20
LOAD_DURATION="2m"
SAMPLE_INTERVAL_SECONDS=2
LIGHTHOUSE_USER_ID="4939a0b9a7742e2cc52289e0"
OPENID_CONFIG_URL="https://samples.auth0.com/.well-known/openid-configuration"
ROOT_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
# the Python MSS and the backend are released with; uv would otherwise take the newest it can
# find or download, whose wheels may not exist yet
export UV_PYTHON="${UV_PYTHON:-3.13}"
FIXTURES_PATH="$ROOT_PATH/ui/fixtures"
MSS_PATH="$ROOT_PATH"
DASHBOARD_PATH="$MSS_PATH/ui"
MSS_PORT=8002
MONGO_PORT=27019
REDIS_PORT=6381

main() {
  [[ -n "$1" ]] || exit_with_err "usage: $0 <out-dir>"
  for tool in node uv mongod mongosh redis-server redis-cli; do
    command -v "$tool" &> /dev/null || exit_with_err "$tool is not available"
  done
  mkdir -p "$1"
  OUT_PATH="$(cd "$1" && pwd)"

  [[ "${2:-dashboard}" != "dashboard" ]] || record_dashboard
  [[ "${2:-mss}" != "mss" ]] || record_mss
}

record_dashboard() {
  # MSS serves the dashboard's build, so it is made before MSS starts
  (cd "$DASHBOARD_PATH" && npm run build -- --mode test > /dev/null)
  start_stack
  local cookie
  cookie="$(sign_session)"
  rm -rf "$OUT_PATH/lighthouse"
  (cd "$DASHBOARD_PATH" \
    && npx --yes "@lhci/cli@$LHCI_VERSION" collect --config="$ROOT_PATH/dev/perf/lighthouserc.json" \
      --settings.extraHeaders="{\"Cookie\":\"$cookie\"}" \
    && npx --yes "@lhci/cli@$LHCI_VERSION" upload --target=filesystem --outputDir="$OUT_PATH/lighthouse")
  keep_representative_reports
  stop_stack
}

record_mss() {
  start_stack
  sample_processes &
  sampler_pid=$!
  sample_connections &
  connections_pid=$!
  uvx --from "locust==$LOCUST_VERSION" --with pymongo --with pyjwt \
    locust -f "$ROOT_PATH/dev/perf/locustfile.py" --headless --only-summary \
    --host "http://127.0.0.1:$MSS_PORT" -u "$LOAD_USERS" -r "$LOAD_USERS" -t "$LOAD_DURATION" \
    --csv "$OUT_PATH/locust"
  stop_stack
}

# Starts MongoDB, Redis and MSS, each of its own, in WORK_PATH, seeding MSS's database from the fixtures
start_stack() {
  WORK_PATH="$(mktemp -d)"
  trap stop_stack EXIT
  sed -e "s|mongodb://tergite-mongo:27017|mongodb://127.0.0.1:$MONGO_PORT|" \
    -e "s|redis://tergite-redis:6379|redis://127.0.0.1:$REDIS_PORT|" -e "s|bcc_certs/|$FIXTURES_PATH/|" \
    -e "s|OPENID_CONFIG_URL|$OPENID_CONFIG_URL|" -e "s|OPENID_CLIENT_ID|perf|" \
    -e "s|OPENID_CLIENT_SECRET|perf|" "$FIXTURES_PATH/mss-config.toml" > "$WORK_PATH/mss-config.toml"

  mkdir "$WORK_PATH/mongo"
  mongod --dbpath "$WORK_PATH/mongo" --port "$MONGO_PORT" --bind_ip 127.0.0.1 > "$WORK_PATH/mongod.log" 2>&1 &
  mongo_pid=$!
  redis-server --port "$REDIS_PORT" --bind 127.0.0.1 --save "" --appendonly no > "$WORK_PATH/redis.log" 2>&1 &
  redis_pid=$!
  until mongosh --quiet --port "$MONGO_PORT" --eval "db.runCommand('ping').ok" &> /dev/null; do sleep 0.5; done

  UV_PROJECT_ENVIRONMENT="$WORK_PATH/venv" uv sync -q --frozen --no-dev --project "$MSS_PATH"
  export MSS_CONFIG_FILE="$WORK_PATH/mss-config.toml" PRIVATE_KEY_FILE="$FIXTURES_PATH/private-mss-key.pem"
  (cd "$MSS_PATH" && "$WORK_PATH/venv/bin/python" -m dev.seed) > "$WORK_PATH/seed.log" 2>&1
  start_mss
  until curl -sf "http://127.0.0.1:$MSS_PORT/health" > /dev/null; do
    kill -0 "$mss_pid" 2> /dev/null || exit_with_err "MSS stopped; see $WORK_PATH/mss.log"
    sleep 0.5
  done
}

# Migrates the database and serves MSS from MSS_PATH, setting mss_pid
start_mss() {
  (cd "$MSS_PATH" && exec "$WORK_PATH/venv/bin/python" main.py start --host 127.0.0.1 --port "$MSS_PORT") \
    > "$WORK_PATH/mss.log" 2>&1 &
  mss_pid=$!
}

stop_stack() {
  kill $sampler_pid $connections_pid "$mss_pid" "$redis_pid" "$mongo_pid" 2> /dev/null
  wait 2> /dev/null
  rm -rf "$WORK_PATH"
  sampler_pid="" connections_pid=""
  trap - EXIT
}
# Writes a row of each process's CPU and resident memory to process-stats.csv every
# SAMPLE_INTERVAL_SECONDS, the CPU being its share of a core over that interval
sample_processes() {
  uv run -q --no-project --with psutil python - "$OUT_PATH/process-stats.csv" "$SAMPLE_INTERVAL_SECONDS" \
    "mss=$mss_pid" "mongodb=$mongo_pid" "redis=$redis_pid" <<'PYTHON'
import csv
import sys
import time

import psutil

path, interval, *named_pids = sys.argv[1:]
processes = {
    name: psutil.Process(int(pid))
    for name, pid in (named_pid.split("=") for named_pid in named_pids)
}
for process in processes.values():
    process.cpu_percent()
with open(path, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["time", "process", "cpu", "memory"])
    # until stop_mss stops the processes
    while all(process.is_running() for process in processes.values()):
        time.sleep(float(interval))
        now = int(time.time())
        try:
            for name, process in processes.items():
                memory = process.memory_info().rss / 2**20
                writer.writerow([now, name, f"{process.cpu_percent():.2f}%", f"{memory:.1f}MiB"])
        except psutil.NoSuchProcess:
            break
        file.flush()
PYTHON
}

# Appends the open connections of each database to connections.csv every SAMPLE_INTERVAL_SECONDS
sample_connections() {
  echo "time,database,connections" > "$OUT_PATH/connections.csv"
  while true; do
    local now
    now="$(date +%s)"
    echo "$now,mongodb,$(mongosh --quiet --port "$MONGO_PORT" \
      --eval 'db.serverStatus().connections.current')" >> "$OUT_PATH/connections.csv"
    echo "$now,redis,$(redis-cli -p "$REDIS_PORT" info clients \
      | awk -F: '/^connected_clients/ {print $2}' | tr -d '\r')" >> "$OUT_PATH/connections.csv"
    sleep "$SAMPLE_INTERVAL_SECONDS"
  done
}

# Keeps the JSON report of each page's median run, which compare.py reads, and drops the rest
keep_representative_reports() {
  python3 - "$OUT_PATH/lighthouse" <<'PYTHON'
import json, sys
from pathlib import Path

folder = Path(sys.argv[1])
entries = json.loads((folder / "manifest.json").read_text())
kept = [
    {**v, "jsonPath": Path(v["jsonPath"]).name, "htmlPath": None}
    for v in entries
    if v["isRepresentativeRun"]
]
for path in folder.iterdir():
    if path.name != "manifest.json" and path.name not in {v["jsonPath"] for v in kept}:
        path.unlink()
(folder / "manifest.json").write_text(json.dumps(kept, indent=2))
PYTHON
}

# Prints the session cookie of LIGHTHOUSE_USER_ID, signed with the secret of MSS's config
sign_session() {
  uv run -q --no-project --with pyjwt python - "$WORK_PATH/mss-config.toml" "$FIXTURES_PATH/users.json" \
    "$LIGHTHOUSE_USER_ID" <<'PYTHON'
import json, sys, time, tomllib

import jwt

config_path, users_path, user_id = sys.argv[1:]
auth = tomllib.load(open(config_path, "rb"))["auth"]
user = next(v for v in json.load(open(users_path)) if v["id"] == user_id)
claims = {"sub": user_id, "roles": user["roles"], "aud": ["fastapi-users:auth"], "exp": int(time.time()) + 3600}
print(f"{auth['cookie_name']}={jwt.encode(claims, auth['jwt_secret'], algorithm='HS256')}")
PYTHON
}

exit_with_err() {
  echo "$(date +'%Y-%m-%d %H:%M:%S') - ERROR: $1" >&2
  exit 1
}

main "$@"
