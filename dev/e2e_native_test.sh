#!/bin/bash
# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Runs the dashboard's Playwright suite against the whole stack, each service running natively:
# MongoDB seeded from the dashboard's fixtures/, Redis, MSS from this checkout serving the
# dashboard's test build at /ui, and the backends from a tergite-backend checkout, one process
# serving them all, each under its own path, all from fresh data in temp-native/. Its arguments
# go to `playwright test`, e.g. a spec to run or --update-snapshots.
# Needs mongod, mongosh, redis-server, sqlite3, uv, npm, jq and curl.
#
# Usage
# =====
#
# BACKEND_PATH="../tergite-backend" \ # a tergite-backend checkout to run; or else BACKEND_REPO is cloned
#   BACKEND_REPO="https://github.com/tergite/tergite-backend.git" \
#   BACKEND_BRANCH="main" \ # the branch of BACKEND_REPO to clone; default is 'main'
#   DEBUG="True" \ # Set 'True' to keep the services running and temp-native/ after the tests, default: ''
#   VISUAL="True" \ # Set 'True' to run the e2e in Playwright's UI mode, default: ''
#   OPENID_CONFIG_URL="https://samples.auth0.com/.well-known/openid-configuration" \ # MSS's mock OpenID provider
#   OPENID_CLIENT_ID="kbyuFDidLLm280LIwVFiazOqjO3ty8KH" \ # its client ID
#   OPENID_CLIENT_SECRET="60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa" \ # its client secret
#   OPENID_AUTH_URL="https://samples.auth0.com/authorize" \ # the URL it redirects to for logging in
#   ./dev/e2e_native_test.sh

set -e # exit if any step fails

ROOT_PATH="$(cd "$(dirname "$0")/.." && pwd)"
WORK_PATH="$ROOT_PATH/temp-native"
FIXTURES_PATH="$ROOT_PATH/apps/tergite-mss/ui/fixtures"
DASHBOARD_PATH="$ROOT_PATH/apps/tergite-mss/ui"
MSS_PATH="$ROOT_PATH/apps/tergite-mss"
BACKEND_REPO="$BACKEND_REPO"
BACKEND_BRANCH="${BACKEND_BRANCH:-main}"
OPENID_CONFIG_URL="${OPENID_CONFIG_URL:-https://samples.auth0.com/.well-known/openid-configuration}"
OPENID_CLIENT_ID="${OPENID_CLIENT_ID:-kbyuFDidLLm280LIwVFiazOqjO3ty8KH}"
OPENID_CLIENT_SECRET="${OPENID_CLIENT_SECRET:-60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa}"
OPENID_AUTH_URL="${OPENID_AUTH_URL:-https://samples.auth0.com/authorize}"
# the dashboard's test build calls MSS at 8002, and the tests reset the data at 3001
MSS_PORT=8002
RESET_PORT=3001
MONGO_PORT=27018
REDIS_PORT=6380
BACKEND_PORT=8101
LOKI_JWT_SECRET="e9fae9efa7c3ff10348acde323baa5273db8021712ecb1f59fdf0e8336240fb7d70c6d8d"
# name|executor|app settings|JWT secret|max slot|min slot|slots a day|idle time; empty fields
# keep the backend's defaults
BACKENDS=(
  "qiskit_pulse_2q|qiskit_pulse_2q|production|$LOKI_JWT_SECRET||||"
  "qiskit_pulse_1q|qiskit_pulse_1q|production|dd94de9017e976973769aaf5d426fdb95cab46feda584dbdbc5f3f02bbf8ae8ce77211d7||||"
  "Loke|quantify|staging|$LOKI_JWT_SECRET|7200|1200|20|100"
  "Thor|quantify|staging|$LOKI_JWT_SECRET|7200|600|20|100"
  "Pingu|quantify|staging|$LOKI_JWT_SECRET|9600|300|25|100"
  "Pegu|quantify|staging|$LOKI_JWT_SECRET|7200|1200|24|100"
  "Likee|quantify|staging|$LOKI_JWT_SECRET|7200|1200|24|100"
  "Thea|quantify|staging|$LOKI_JWT_SECRET|7200|1200|24|100"
)
# the backends whose databases a reset reloads
RESET_BACKENDS=(qiskit_pulse_2q qiskit_pulse_1q Loke Thor Pingu Pegu)
PIDS=()

# Logging function for errors
log_error() {
  echo "$(date +'%Y-%m-%d %H:%M:%S') - ERROR: $1" >&2
}

# exits the program with an error
# usage:
#   exit_with_err "some string"
exit_with_err() {
  log_error "$1";
  exit 1;
}

for tool in mongod mongosh redis-server sqlite3 uv npm jq curl; do
  command -v "$tool" &> /dev/null || exit_with_err "$tool is not available"
done

# replaces the given string in a given file with another string
# usage:
#   replace_str file "original string" "new string"
replace_str() {
  if [[ "$(uname -s)" = "Darwin" ]]; then
    sed -i "" "s|$2|$3|" "$1";
  else
    sed -i "s|$2|$3|" "$1";
  fi
}

# reads the JSON file and returns it as an escaped string
# usage:
#   read_json file
read_json() {
  echo "$(jq -c . $1 | jq -Rr @sh)"
}

# starts a command in the background, logging to temp-native/logs/<name>.log, and sets
# SERVICE_PID to its process ID
# usage:
#   start_service name command [args...]
start_service() {
  local name=$1;
  shift;
  "$@" > "$WORK_PATH/logs/$name.log" 2>&1 &
  SERVICE_PID=$!;
  PIDS+=($SERVICE_PID);
}

# waits until the URL answers with any HTTP status, failing if the service's process exits
# or it takes over a minute
# usage:
#   wait_for_url name url pid
wait_for_url() {
  local deadline=$(( $(date +%s) + 60 ));
  until [[ "$(curl -s -o /dev/null -w '%{http_code}' "$2")" != "000" ]]; do
    kill -0 "$3" 2>/dev/null || exit_with_err "$1 stopped; see temp-native/logs/$1.log";
    [[ $(date +%s) -lt $deadline ]] || exit_with_err "$1 did not start; see temp-native/logs/$1.log";
    sleep 0.5;
  done
}

# stops the services, and removes temp-native/ but its environments, unless DEBUG is set
# usage:
#   stop_stack
stop_stack() {
  if [[ $(echo "${DEBUG}" | tr '[:lower:]' '[:upper:]') = "TRUE" ]]; then
    echo "Not stopping the services, $(IFS=' '; echo "${PIDS[*]}"), because DEBUG=$DEBUG";
    return;
  fi
  echo "Stopping the services"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true;
  done
  wait 2>/dev/null || true;
  find "$WORK_PATH" -mindepth 1 -maxdepth 1 ! -name venvs -exec rm -rf {} +;
}

for port in $MSS_PORT $RESET_PORT $MONGO_PORT $REDIS_PORT $BACKEND_PORT; do
  ! (exec 3<> "/dev/tcp/127.0.0.1/$port") 2> /dev/null || exit_with_err "port $port is in use"
done

trap stop_stack EXIT

echo "Creating $WORK_PATH"
find "$WORK_PATH" -mindepth 1 -maxdepth 1 ! -name venvs -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$WORK_PATH/logs" "$WORK_PATH/mongo" "$WORK_PATH/venvs"

if [[ -n "$BACKEND_PATH" ]]; then
  BACKEND_PATH="$(cd "$BACKEND_PATH" && pwd)"
elif [[ -z "$BACKEND_REPO" ]]; then
  exit_with_err "set BACKEND_PATH or BACKEND_REPO"
else
  echo "Cloning the backend..."
  git clone -q --single-branch --branch "$BACKEND_BRANCH" "$BACKEND_REPO" "$WORK_PATH/tergite-backend"
  BACKEND_PATH="$WORK_PATH/tergite-backend"
fi

# environments of their own, so that a checkout's .venv stays as it is; the backends' API needs
# neither executor's extra
echo "Installing MSS and the backend"
UV_PROJECT_ENVIRONMENT="$WORK_PATH/venvs/mss" uv sync -q --frozen --no-dev --project "$MSS_PATH"
UV_PROJECT_ENVIRONMENT="$WORK_PATH/venvs/backend" uv sync -q --frozen --no-dev --project "$BACKEND_PATH"

echo "Starting MongoDB and Redis"
# The TTL monitor runs every second, not every minute, so that the expired notices
# are gone before a test asks for them
start_service mongod mongod --dbpath "$WORK_PATH/mongo" --port $MONGO_PORT --bind_ip 127.0.0.1 \
  --setParameter ttlMonitorSleepSecs=1
start_service redis redis-server --port $REDIS_PORT --bind 127.0.0.1 --save "" --appendonly no
until mongosh --quiet --port $MONGO_PORT --eval "db.runCommand('ping').ok" &> /dev/null; do sleep 0.5; done

cp "$FIXTURES_PATH/mongo-init.js" "$WORK_PATH/mongo-init.js"
replace_str "$WORK_PATH/mongo-init.js" "rawCalibrations = \"\[\]\"" "rawCalibrations = $(read_json $FIXTURES_PATH/calibrations.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawDevices = \"\[\]\"" "rawDevices = $(read_json $FIXTURES_PATH/device-list.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawJobs = \"\[\]\"" "rawJobs = $(read_json $FIXTURES_PATH/jobs.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawNotices = \"\[\]\"" "rawNotices = $(read_json $FIXTURES_PATH/notices.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawProjects = \"\[\]\"" "rawProjects = $(read_json $FIXTURES_PATH/projects.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawTokens = \"\[\]\"" "rawTokens = $(read_json $FIXTURES_PATH/tokens.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawUserRequests = \"\[\]\"" "rawUserRequests = $(read_json $FIXTURES_PATH/user-requests.json)"
replace_str "$WORK_PATH/mongo-init.js" "rawUsers = \"\[\]\"" "rawUsers = $(read_json $FIXTURES_PATH/users.json)"
mongosh --quiet --port $MONGO_PORT "$WORK_PATH/mongo-init.js" > /dev/null

echo "Building the dashboard, which MSS serves"
(cd "$DASHBOARD_PATH" && { [[ -d node_modules ]] || npm ci; } \
  && npm run build -- --mode test > "$WORK_PATH/logs/dashboard-build.log")

echo "Starting MSS"
cp "$FIXTURES_PATH/mss-config.toml" "$WORK_PATH/mss-config.toml"
replace_str "$WORK_PATH/mss-config.toml" "mongodb://tergite-mongo:27017" "mongodb://127.0.0.1:$MONGO_PORT"
replace_str "$WORK_PATH/mss-config.toml" "redis://tergite-redis:6379" "redis://127.0.0.1:$REDIS_PORT"
replace_str "$WORK_PATH/mss-config.toml" "bcc_certs/" "$FIXTURES_PATH/"
replace_str "$WORK_PATH/mss-config.toml" "OPENID_CLIENT_ID" "$OPENID_CLIENT_ID"
replace_str "$WORK_PATH/mss-config.toml" "OPENID_CLIENT_SECRET" "$OPENID_CLIENT_SECRET"
replace_str "$WORK_PATH/mss-config.toml" "OPENID_CONFIG_URL" "$OPENID_CONFIG_URL"
# the backend process serves each device at /<its DEFAULT_PREFIX>
for backend in "${BACKENDS[@]}"; do
  IFS="|" read -r name _ <<< "$backend"
  host="$(echo "$name" | tr '[:upper:]' '[:lower:]')"
  replace_str "$WORK_PATH/mss-config.toml" "http://$host:8000" "http://127.0.0.1:$BACKEND_PORT/$name"
done
export MSS_CONFIG_FILE="$WORK_PATH/mss-config.toml" PRIVATE_KEY_FILE="$FIXTURES_PATH/private-mss-key.pem"
start_service mss bash -c "cd '$MSS_PATH' && exec '$WORK_PATH/venvs/mss/bin/python' main.py start --host 127.0.0.1 --port $MSS_PORT"
mss_pid=$SERVICE_PID
unset MSS_CONFIG_FILE PRIVATE_KEY_FILE
wait_for_url mss "http://127.0.0.1:$MSS_PORT/" $mss_pid

echo "Starting the backends"
reset_databases=()
env_file_args=()
for backend in "${BACKENDS[@]}"; do
  IFS="|" read -r name executor app_settings jwt_secret max_slot min_slot slots_a_day idle_time <<< "$backend"
  stem="$(echo "$name" | tr '[:upper:]' '[:lower:]')"
  dir="$WORK_PATH/backends/$name"
  mkdir -p "$dir/storage"
  {
    echo "BCC_DEFAULT_PREFIX=$name"
    echo "BCC_EXECUTOR_TYPE=$executor"
    echo "BCC_APP_SETTINGS=$app_settings"
    echo "BCC_JWT_SECRET=$jwt_secret"
    echo "BCC_CORS_ORIGINS=127.0.0.1,localhost"
    echo "BCC_MACHINE_ROOT_URL=http://127.0.0.1:$BACKEND_PORT/$name"
    echo "BCC_MSS_MACHINE_ROOT_URL=http://127.0.0.1:$MSS_PORT"
    echo "BCC_REDIS_HOST=127.0.0.1"
    echo "BCC_REDIS_PORT=$REDIS_PORT"
    echo "BCC_STORAGE_ROOT=$dir/storage"
    echo "BCC_BOOKING_DB_URL=sqlite:///$dir/booking_db.db"
    echo "BCC_BACKEND_SETTINGS=$FIXTURES_PATH/$stem.toml"
    echo "BCC_CALIBRATION_SEED=$FIXTURES_PATH/$stem.seed.toml"
    echo "BCC_PRIVATE_KEY_FILE=$FIXTURES_PATH/private-$(echo "$stem" | tr '_' '-')-key.pem"
    echo "BCC_MSS_PUBLIC_KEY_PATH=$FIXTURES_PATH/public-mss-key.pem"
    [[ -z "$max_slot" ]] || echo "BCC_MAX_TIME_SLOT_LENGTH=$max_slot"
    [[ -z "$min_slot" ]] || echo "BCC_MIN_TIME_SLOT_LENGTH=$min_slot"
    [[ -z "$slots_a_day" ]] || echo "BCC_MAX_SLOTS_PER_DAY=$slots_a_day"
    [[ -z "$idle_time" ]] || echo "BCC_MAX_IDLE_TIME=$idle_time"
    [[ "$app_settings" != "staging" ]] || echo "BCC_CURRENT_DATE=2025-10-01T00:00:00.000Z"
  } > "$dir/backend.env"
  env_file_args+=(--env-file "$dir/backend.env")
  [[ ! " ${RESET_BACKENDS[*]} " =~ " $name " ]] || reset_databases+=("$dir/booking_db.db")
done
start_service backends bash -c "cd '$WORK_PATH/backends' && exec '$WORK_PATH/venvs/backend/bin/python' '$BACKEND_PATH/main.py' serve --host 127.0.0.1 --port $BACKEND_PORT ${env_file_args[*]}"
wait_for_url backends "http://127.0.0.1:$BACKEND_PORT/docs" $SERVICE_PID

echo "Starting the reset service"
start_service reset "$WORK_PATH/venvs/mss/bin/python" "$ROOT_PATH/dev/e2e_reset_server.py" \
  --port $RESET_PORT --mongo-port $MONGO_PORT --mongo-init-script "$WORK_PATH/mongo-init.js" \
  --sql "$FIXTURES_PATH/backend_db.sql" "${reset_databases[@]}"
reset_pid=$SERVICE_PID
wait_for_url reset "http://127.0.0.1:$RESET_PORT/" $reset_pid

echo "Running end-to-end test suite..."
cd "$DASHBOARD_PATH"
npx playwright install chromium > /dev/null
export DASHBOARD_URL="http://127.0.0.1:$MSS_PORT/ui/"
export DB_RESET_URL="http://127.0.0.1:$RESET_PORT/refreshed-db"
export OPENID_AUTH_URL
if [[ $(echo "${VISUAL}" | tr '[:lower:]' '[:upper:]') = "TRUE" ]]; then
  npx playwright test --ui "$@"
else
  npx playwright test "$@"
fi

echo "Script completed."
