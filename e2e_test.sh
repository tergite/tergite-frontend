#!/bin/bash
# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# Usage
# =====
#
# BACKEND_REPO="https://github.com/tergite/tergite-backend.git" \
#   BACKEND_BRANCH="main" \ # you can set a different backend branch; default is 'main'
#   DEBUG="True" \ # Set 'True' to avoid cleaning up the containers, env, and repos after test, default: ''
#   VISUAL="True" \ # Set 'True' to see the e2e in a graphical user interface, default: ''
#   CYPRESS_IMAGE="cypress/base:20.17.0" \ # Set the docker image to run the tests. If not provided, it runs on the host machine
#   OPENID_CONFIG_URL="https://samples.auth0.com/.well-known/openid-configuration" \ # Set the url to get the openID config for mock OpenID connect, default: 'https://samples.auth0.com/.well-known/openid-configuration'
#   OPENID_CLIENT_ID="kbyuFDidLLm280LIwVFiazOqjO3ty8KH" \ # Set the client id for mock OpenID connect, default: 'kbyuFDidLLm280LIwVFiazOqjO3ty8KH'
#   OPENID_CLIENT_SECRET="60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa" \ # Set the client secret for mock OpenID connect, default: '60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa'
#   OPENID_AUTH_URL="https://samples.auth0.com/authorize" \ # Set the url to redirect to for auth for mock OpenID connect, default: 'https://samples.auth0.com/authorize'
#   ./e2e_test.sh

set -e # exit if any step fails

# Global variables
TEMP_DIR="temp"
BACKEND_REPO="$BACKEND_REPO"
BACKEND_BRANCH="${BACKEND_BRANCH:-main}"
OPENID_CONFIG_URL="${OPENID_CONFIG_URL:-https://samples.auth0.com/.well-known/openid-configuration}"
OPENID_CLIENT_ID="${OPENID_CLIENT_ID:-kbyuFDidLLm280LIwVFiazOqjO3ty8KH}"
OPENID_CLIENT_SECRET="${OPENID_CLIENT_SECRET:-60Op4HFM0I8ajz0WdiStAbziZ-VFQttXuxixHHs2R7r7-CW8GR79l-mmLqMhc-Sa}"
OPENID_AUTH_URL="${OPENID_AUTH_URL:-https://samples.auth0.com/authorize}"
APP_TOKEN="W0imS_n_J5ZwP8wFYvbBCiDkJVhQcEROEfyTPvFko1E"
ROOT_PATH="$(pwd)"
TEMP_DIR_PATH="$ROOT_PATH/$TEMP_DIR"
FIXTURES_PATH="$ROOT_PATH/apps/tergite-dashboard/cypress/fixtures"
CYPRESS_IMAGE="$CYPRESS_IMAGE"

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

# Check that docker is available
docker info &> /dev/null || exit_with_err "docker is not running"

# Check that jq is available
jq --version &> /dev/null || exit_with_err "jq is not available"

# Check that git is available
git --version &> /dev/null || exit_with_err "git is not available"

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
  # the sed is to escape single quotes properly for javascript
  echo "$(jq -c . $1 | jq -Rr @sh)"
}


# Clean up any remaining docker things
echo "Cleaning up docker artefacts from previous runs"
docker compose -p tergite-frontend-e2e  down --rmi all --volumes 2>/dev/null
docker rmi -f tergite/tergite-mss 2>/dev/null
docker rmi -f tergite/tergite-dashboard 2>/dev/null
docker rmi -f tergite/tergite-backend-e2e:latest 2>/dev/null
docker rmi -f tergite/tergite-backend-with-db-e2e:latest 2>/dev/null
docker system prune -f

# Create and navigating to temporary directory
echo "Creating temporary folder $TEMP_DIR_PATH"
rm -rf "$TEMP_DIR_PATH"
mkdir "$TEMP_DIR_PATH"
cd "$TEMP_DIR_PATH"

# Setting up the repositories
echo "Cloning repositories..."
rm -rf tergite-frontend
rm -rf tergite-backend
git clone "$ROOT_PATH" tergite-frontend
git clone --single-branch --branch "$BACKEND_BRANCH" "$BACKEND_REPO"

# Adding special docker file to tergite-backend folder
echo "Adding configuraiton files to tergite-backend"
cd tergite-backend
cat "Dockerfile" "$FIXTURES_PATH/backend-with-db.Dockerfile" > "Dockerfile.with-db"
cp "$FIXTURES_PATH/sqlite-router.sh" .
cd ..

# Adding configuration files to tergite-frontend folder
echo "Adding configuration files to tergite-frontend"
cd tergite-frontend
cp "$FIXTURES_PATH/mongo-init.js" .
cp "$FIXTURES_PATH/mongo-router.sh" .
cp "$FIXTURES_PATH/mongo.Dockerfile" .
cp "$FIXTURES_PATH/e2e-docker-compose.yml" .
cp "$FIXTURES_PATH/qiskit_pulse_1q.toml" .
cp "$FIXTURES_PATH/qiskit_pulse_1q.seed.toml" .
cp "$FIXTURES_PATH/qiskit_pulse_2q.toml" .
cp "$FIXTURES_PATH/qiskit_pulse_2q.seed.toml" .
cp "$FIXTURES_PATH/generic.seed.toml" .
cp "$FIXTURES_PATH/loke.toml" .
cp "$FIXTURES_PATH/loke.seed.toml" .
cp "$FIXTURES_PATH/thor.toml" .
cp "$FIXTURES_PATH/thor.seed.toml" .
cp "$FIXTURES_PATH/pingu.toml" .
cp "$FIXTURES_PATH/pingu.seed.toml" .
cp "$FIXTURES_PATH/pegu.toml" .
cp "$FIXTURES_PATH/likee.toml" .
cp "$FIXTURES_PATH/likee.seed.toml" .
cp "$FIXTURES_PATH/thea.toml" .
cp "$FIXTURES_PATH/thea.seed.toml" .
cp "$FIXTURES_PATH/booking_db.db" qiskit_pulse_1q_booking_db.db
cp "$FIXTURES_PATH/booking_db.db" qiskit_pulse_2q_booking_db.db
cp "$FIXTURES_PATH/backend_db.sql" .
cp "$FIXTURES_PATH/private-mss-key.pem" .
cp "$FIXTURES_PATH/public-mss-key.pem" .
cp "$FIXTURES_PATH/quantify-config.json" .
cp "$FIXTURES_PATH/quantify-metadata.yml" .
cp "$FIXTURES_PATH/e2e.env" .env
printf "\nMSS_APP_TOKEN=\"$APP_TOKEN\"" >> .env
cp "$FIXTURES_PATH/mss-config.toml" .

# Update the mongo-init.js to include the JSON data from the fixtures
replace_str mongo-init.js "rawCalibrations = \"\[\]\"" "rawCalibrations = $(read_json $FIXTURES_PATH/calibrations.json)"
replace_str mongo-init.js "rawDevices = \"\[\]\"" "rawDevices = $(read_json $FIXTURES_PATH/device-list.json)"
replace_str mongo-init.js "rawJobs = \"\[\]\"" "rawJobs = $(read_json $FIXTURES_PATH/jobs.json)"
replace_str mongo-init.js "rawProjects = \"\[\]\"" "rawProjects = $(read_json $FIXTURES_PATH/projects.json)"
replace_str mongo-init.js "rawTokens = \"\[\]\"" "rawTokens = $(read_json $FIXTURES_PATH/tokens.json)"
replace_str mongo-init.js "rawUserRequests = \"\[\]\"" "rawUserRequests = $(read_json $FIXTURES_PATH/user-requests.json)"
replace_str mongo-init.js "rawUsers = \"\[\]\"" "rawUsers = $(read_json $FIXTURES_PATH/users.json)"

# Update the .env.test in tergite dashboard
replace_str apps/tergite-dashboard/.env.test "DB_RESET_URL=\"http://127.0.0.1:8002/refreshed-db\"" "DB_RESET_URL=\"http://127.0.0.1:3001/refreshed-db\"";
replace_str apps/tergite-dashboard/.env.test "OPENID_AUTH_URL=\"OPENID_AUTH_URL\"" "OPENID_AUTH_URL=\"$OPENID_AUTH_URL\"";
if [[ -n "$TEST_THRESHOLD" ]]; then 
  printf "\nTEST_THRESHOLD=$TEST_THRESHOLD" >> apps/tergite-dashboard/.env.test; 
fi

# Update the .env in tergite dashboard. This will update such things as VITE_REFETCH_INTERVAL_MS, etc.
cp apps/tergite-dashboard/.env.test apps/tergite-dashboard/.env;

# Update cypress.config.ts in tergite dashboard
#  set the dashboard URL to the URL of the dashboard service
replace_str apps/tergite-dashboard/cypress.config.ts "http://127.0.0.1:5173" "http://127.0.0.1:3000";

# Update mss-config.toml
replace_str mss-config.toml "OPENID_CLIENT_ID" "$OPENID_CLIENT_ID";
replace_str mss-config.toml "OPENID_CLIENT_SECRET" "$OPENID_CLIENT_SECRET";
replace_str mss-config.toml "OPENID_CONFIG_URL" "$OPENID_CONFIG_URL";

# Starting services in the tergite-frontend folder
echo "Starting all e2e services"
docker compose \
  -f fresh-docker-compose.yml \
  -f e2e-docker-compose.yml \
  -p tergite-frontend-e2e \
  up -d;

# Run in python docker file if $CYPRESS_IMAGE is set
# or else run on host machine

if [[ -z "$CYPRESS_IMAGE" ]]; then
  # Starting the tests
  echo "Installing dependencies..."
  cd "$TEMP_DIR_PATH/tergite-frontend/apps/tergite-dashboard"
  npm ci

  echo "Running end-to-end test suite..."
  if [[ $(echo "${VISUAL}" | tr '[:lower:]' '[:upper:]') = "TRUE" ]]; then 
    npm run visual-cypress-only;
  else 
    npm run cypress-only;
  fi

else
  if [[ $(echo "${VISUAL}" | tr '[:lower:]' '[:upper:]') = "TRUE" ]]; then 
    exit_with_err "Cannot run visually when a CYPRESS_IMAGE is set. Set VISUAL='' or remove CYPRESS_IMAGE";
  fi 

  echo "Running e2e tests..."
  cd "$TEMP_DIR_PATH/tergite-frontend/apps/tergite-dashboard"
  docker run \
    --name tergite-frontend-e2e-runner \
    --network=host \
    -v "$PWD":/app -w /app \
    "$CYPRESS_IMAGE" bash -c "set -e; npm ci; npm run cypress-only;";
fi

# Cleanup
# In order to debug the containers and the repos,
# set the env variable "DEBUG" to True
if [[ $(echo "${DEBUG}" | tr '[:lower:]' '[:upper:]') != "TRUE" ]]; then
  echo "Cleaning up..."
  docker compose -p tergite-frontend-e2e down --rmi all --volumes
  docker rm -f tergite-frontend-e2e-runner 2>/dev/null || true
  rm -rf "$TEMP_DIR_PATH" || true
else
  echo "Not deleting the containers and repositories because DEBUG=$DEBUG"
fi

echo "Script completed."
