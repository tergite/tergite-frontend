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
# Copies tergite-backend's committed OpenAPI schema, then regenerates MSS's models of the
# events a backend sends: from the repo root, `dev/openapi/sync.sh`, with tergite-backend beside
# this repo or BACKEND_PATH naming its checkout.

set -e # exit if any step fails

ROOT_PATH="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_PATH="${BACKEND_PATH:-$ROOT_PATH/../tergite-backend}"

cp "$BACKEND_PATH/dev/openapi/openapi.json" "$ROOT_PATH/dev/openapi/bcc.json"
cd "$ROOT_PATH" && uv run --frozen python -m dev.openapi.generate
