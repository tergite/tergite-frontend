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
# Starts MSS from this checkout with `main.py start`, which migrates the database and serves,
# passing on its arguments: from apps/tergite-mss, `./start_mss.sh` or `./start_mss.sh --reload`.
# It reads the config MSS_CONFIG_FILE names, mss-config.toml by default, which a SOPS file
# encrypted with a Hashicorp Vault key may be: that needs sops, yq, VAULT_ADDR and VAULT_TOKEN.

set -e

cd "$(dirname "$0")"
config_file="${MSS_CONFIG_FILE:-mss-config.toml}"
if [ -z "$MSS_CONFIG_JSON_STR" ] && [ -f "$config_file" ] && grep -q "hc_vault" "$config_file"; then
	for tool in sops yq; do
		command -v "$tool" > /dev/null || { echo "$tool is needed to decrypt $config_file" >&2; exit 1; }
	done
	# MSS reads its config from MSS_CONFIG_JSON_STR when it is set
	MSS_CONFIG_JSON_STR="$(sops decrypt "$config_file" | yq -o=json -p=toml)"
	export MSS_CONFIG_JSON_STR
fi

exec python main.py start "$@"
