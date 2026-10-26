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
# dashboard against the mock API, then Locust on MSS from this working tree, with a MongoDB and
# a Redis of its own, all running natively, both over the e2e fixtures. It samples the CPU and
# memory of the MSS, mongod and redis-server processes, and each database's connections.
#
# Usage
# =====
#
#   ./dev/perf/record.sh dev/perf/baselines           # the baseline
#   ./dev/perf/record.sh /tmp/perf-step-3             # a sign-off run
#   ./dev/perf/record.sh /tmp/perf-step-3 mss         # MSS alone, or dashboard alone
#   python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-step-3
#
# Needs node, uv, mongod, mongosh, redis-server and redis-cli, and ports 8002, 27019 and 6381
# free: the mock API, then MSS, take 8002 in turn; the locustfile reaches MongoDB at 27019.
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
FIXTURES_PATH="$ROOT_PATH/apps/tergite-dashboard/fixtures"
MSS_PATH="$ROOT_PATH/apps/tergite-mss"
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
  cd "$ROOT_PATH/apps/tergite-dashboard"
  local cookie
  cookie="$(sign_mock_session)"
  rm -rf "$OUT_PATH/lighthouse"
  npm run start-e2e-server -- "npx --yes @lhci/cli@$LHCI_VERSION collect \
    --config=$ROOT_PATH/dev/perf/lighthouserc.json \
    --settings.extraHeaders='{\"Cookie\":\"$cookie\"}' \
    && npx --yes @lhci/cli@$LHCI_VERSION upload --target=filesystem --outputDir=$OUT_PATH/lighthouse"
  keep_representative_reports
}

record_mss() {
  WORK_PATH="$(mktemp -d)"
  trap stop_mss EXIT
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
  seed_database

  UV_PROJECT_ENVIRONMENT="$WORK_PATH/venv" uv sync -q --frozen --no-dev --project "$MSS_PATH"
  start_mss
  until curl -sf "http://127.0.0.1:$MSS_PORT/health" > /dev/null; do
    kill -0 "$mss_pid" 2> /dev/null || exit_with_err "MSS stopped; see $WORK_PATH/mss.log"
    sleep 0.5
  done

  sample_processes &
  sampler_pid=$!
  sample_connections &
  connections_pid=$!
  uvx --from "locust==$LOCUST_VERSION" --with pymongo --with pyjwt \
    locust -f "$ROOT_PATH/dev/perf/locustfile.py" --headless --only-summary \
    --host "http://127.0.0.1:$MSS_PORT" -u "$LOAD_USERS" -r "$LOAD_USERS" -t "$LOAD_DURATION" \
    --csv "$OUT_PATH/locust"
}

# Migrates the database and serves MSS from MSS_PATH, setting mss_pid
start_mss() {
  export MSS_CONFIG_FILE="$WORK_PATH/mss-config.toml" PRIVATE_KEY_FILE="$FIXTURES_PATH/private-mss-key.pem"
  (cd "$MSS_PATH" && exec "$WORK_PATH/venv/bin/python" main.py start --host 127.0.0.1 --port "$MSS_PORT") \
    > "$WORK_PATH/mss.log" 2>&1 &
  mss_pid=$!
}

stop_mss() {
  kill "$sampler_pid" "$connections_pid" "$mss_pid" "$redis_pid" "$mongo_pid" 2> /dev/null
  wait 2> /dev/null
  rm -rf "$WORK_PATH"
}

# Runs the e2e mongo-init.js with the fixtures spliced in where it holds "[]"
seed_database() {
  local script="$WORK_PATH/init.js"
  node -e '
    const fs = require("fs");
    const dir = process.argv[1];
    const files = {
      Calibrations: "calibrations", Devices: "device-list", Jobs: "jobs", Notices: "notices",
      Projects: "projects", Tokens: "tokens", UserRequests: "user-requests", Users: "users",
    };
    let script = fs.readFileSync(`${dir}/mongo-init.js`, "utf8");
    for (const [name, file] of Object.entries(files)) {
      const json = fs.readFileSync(`${dir}/${file}.json`, "utf8");
      script = script.replace(`const raw${name} = "[]";`, () => `const raw${name} = ${JSON.stringify(json)};`);
    }
    process.stdout.write(script);
  ' "$FIXTURES_PATH" > "$script"
  mongosh --quiet --port "$MONGO_PORT" "$script" > /dev/null
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

sign_mock_session() {
  npx tsx --env-file=.env.test -e "
    import users from './fixtures/users.json';
    import { generateJwt } from './dev/mock-api/utils';
    const user = users.find((v) => v.id === '$LIGHTHOUSE_USER_ID');
    generateJwt(user, Math.round(Date.now() / 1000) + 3600)
      .then((jwt) => console.log(\`\${process.env.VITE_COOKIE_NAME}=\${jwt}\`));
  "
}

exit_with_err() {
  echo "$(date +'%Y-%m-%d %H:%M:%S') - ERROR: $1" >&2
  exit 1
}

main "$@"
