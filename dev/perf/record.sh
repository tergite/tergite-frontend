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
# Records the performance measures of REFACTOR.md step 1.7 into <out-dir>: Lighthouse on the
# dashboard against the mock API, then Locust on MSS in dev/perf/docker-compose.yml, both over
# the e2e fixtures.
#
# Usage
# =====
#
#   ./dev/perf/record.sh dev/perf/baselines           # the baseline
#   ./dev/perf/record.sh /tmp/perf-step-3             # a sign-off run
#   python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-step-3
#
# Needs docker running, and port 8002 free: the mock API, then the MSS container, take it in turn.
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
FIXTURES_PATH="$ROOT_PATH/apps/tergite-dashboard/cypress/fixtures"
COMPOSE=(docker compose -f "$ROOT_PATH/dev/perf/docker-compose.yml")

main() {
  [[ -n "$1" ]] || exit_with_err "usage: $0 <out-dir>"
  docker info &> /dev/null || exit_with_err "docker is not running"
  mkdir -p "$1"
  OUT_PATH="$(cd "$1" && pwd)"

  record_dashboard
  record_mss
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
  export PERF_MSS_CONFIG_FILE
  PERF_MSS_CONFIG_FILE="$(mktemp)"
  sed -e "s|OPENID_CONFIG_URL|$OPENID_CONFIG_URL|" -e "s|OPENID_CLIENT_ID|perf|" \
    -e "s|OPENID_CLIENT_SECRET|perf|" "$FIXTURES_PATH/mss-config.toml" > "$PERF_MSS_CONFIG_FILE"
  "${COMPOSE[@]}" up -d --build --wait
  trap 'kill "$sampler_pid" 2> /dev/null; "${COMPOSE[@]}" down --volumes; rm "$PERF_MSS_CONFIG_FILE"' EXIT
  seed_database

  sample_resources &
  sampler_pid=$!
  uvx --from "locust==$LOCUST_VERSION" --with pymongo --with pyjwt \
    locust -f "$ROOT_PATH/dev/perf/locustfile.py" --headless --only-summary \
    --host http://127.0.0.1:8002 -u "$LOAD_USERS" -r "$LOAD_USERS" -t "$LOAD_DURATION" \
    --csv "$OUT_PATH/locust"
}

# Runs the e2e mongo-init.js with the fixtures spliced in where it holds "[]"
seed_database() {
  local script
  script="$(mktemp)"
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
  "${COMPOSE[@]}" cp "$script" tergite-mongo:/tmp/init.js
  "${COMPOSE[@]}" exec -T tergite-mongo mongosh --quiet /tmp/init.js > /dev/null
  rm "$script"
}

# Appends one row per container to docker-stats.csv, and the open connections of
# each database to connections.csv, every SAMPLE_INTERVAL_SECONDS
sample_resources() {
  echo "time,container,cpu,memory" > "$OUT_PATH/docker-stats.csv"
  echo "time,database,connections" > "$OUT_PATH/connections.csv"
  while true; do
    local now
    now="$(date +%s)"
    docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}" $("${COMPOSE[@]}" ps -q) \
      | sed "s|^|$now,|" >> "$OUT_PATH/docker-stats.csv"
    echo "$now,mongodb,$("${COMPOSE[@]}" exec -T tergite-mongo mongosh --quiet \
      --eval 'db.serverStatus().connections.current')" >> "$OUT_PATH/connections.csv"
    echo "$now,redis,$("${COMPOSE[@]}" exec -T tergite-redis redis-cli info clients \
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
    import users from './cypress/fixtures/users.json';
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
