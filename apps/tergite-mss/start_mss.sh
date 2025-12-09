#!/bin/bash

# ------------------------------------------------------------------------------
# Private Helpers:
# These start with an underscore and are not meant to be used outside this file
# ------------------------------------------------------------------------------

# Checks if the given software is installed
function _is_installed() {
    command -v "$1" >/dev/null 2>&1;
}

# exit after printing a message to the screen
function _exit_with_error () {
  echo "$1";
  exit 1;
}

# ensures homebrew is installed
function _ensure_brew_exists () {
  if ! _is_installed brew; then 
    echo "installing homebrew first. More details at https://brew.sh/";
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)";
  fi
  return 0;
}

# install a given package via the of the current operating system
# usage:
#   _install_via_pkg_manager <package-to-install>
function _install_via_pkg_manager() {
  local os;
  os="$(uname -s | tr '[:upper:]' '[:lower:]')";
  local package="$1";

  echo "Installing $package";

  if [ "$os" = "darwin" ]; then
    _ensure_brew_exists;
    brew install "$package";
  elif [ "$os" = "linux" ]; then
    if [ -f /etc/os-release ]; then
      # shellcheck source=/dev/null
      . /etc/os-release  # Load variables like $ID and $NAME

      case "$ID" in
        ubuntu|debian)
          apt-get install -y "$package";
          ;;
        fedora)
          dnf install -y "$package";
          ;;
        arch)
          pacman -Sy --noconfirm "$package";
          ;;
        opensuse*|sles)
          zypper install -y "$package";
          ;;
        alpine)
          apk add "$package";
          ;;
        nixos)
          nix-env -i "$package";
          ;;
        *)
          _exit_with_error "no support for unknown distro of linux $ID"
          ;;
      esac
    else 
      _exit_with_error "Unknown linux distro";
    fi
  else 
    _exit_with_error "Unsupported operating system $os";
  fi

  return 0;
}

# installs sops for the current operating system and architecture
# Usage: _install_sops <version>
function _install_sops() {
  local os;
  local raw_arch;
  local version="${1:-v3.10.2}";

  os="$(uname -s | tr '[:upper:]' '[:lower:]')";
  raw_arch="$(uname -m)";

  echo "Installing sops";

  if [ "$os" = "darwin" ]; then
    _ensure_brew_exists;
    brew install sops;
  elif [ "$os" = "linux" ]; then
    # get the right arch name from raw_arch
    case "$raw_arch" in
      x86_64) arch="amd64" ;;
      aarch64 | arm64) arch="arm64" ;;
      armv7l) arch="arm" ;;
      *) _exit_with_error "Unsupported architecture: $raw_arch" ;;
    esac

    if ! _is_installed curl; then 
      _install_via_pkg_manager curl;
    fi

    local binary_name="sops-$version.$os.$arch";
    # Download the binary
    curl -LO "https://github.com/getsops/sops/releases/download/$version/$binary_name";
    # Move the binary in to your PATH
    mv "$binary_name" /usr/local/bin/sops;

    # Make the binary executable
    chmod +x /usr/local/bin/sops;
  else 
    _exit_with_error "Unsupported operating system $os";
  fi

  return 0;
}

# Checks whether the file is encrypted
# Usage: _is_toml_encrypted <file-path>
function _is_toml_encrypted() {
  local file_path="$1";
  if yq -p=json -o=json '.sops' "$file_path" 2> /dev/null | grep "hc_vault" &> /dev/null; then 
    return 0; 
  else 
    return 1; 
  fi
}

# reads the config file into a variable string, decrypting it if it is encrypted
# Usage: _parse_config_file mss-config.toml
function _parse_config_file() {
  local file_path="$1";
  local sops_version="v3.10.2";

  # required software 
  if ! _is_installed yq; then 
    _install_via_pkg_manager "yq" &> /dev/null;
  fi

  if ! _is_installed sops; then 
    _install_sops "$sops_version" &> /dev/null;
  fi 

  if _is_toml_encrypted "$file_path"; then 
    # it picks the VAULT_TOKEN and VAULT_ADDR from the environment
    sops decrypt "$file_path" | yq -o=json -p=toml;
  else
    yq -o=json "$file_path";
  fi 
}

# -------------------------------------------------------------------------------
# Global variables
# -----------------------------------------------------------------------------
__MSS_CONFIG_FILE__="${MSS_CONFIG_FILE:-mss-config.toml}";
__MSS_CONFIG_JSON__="${MSS_CONFIG_JSON_STR:-$(_parse_config_file "$__MSS_CONFIG_FILE__")}";
if [ -z "$__MSS_CONFIG_JSON__" ]; then
  _exit_with_error "MSS config is empty";
fi

# -----------------------------------------------------------------------------
# Main helpers
# -----------------------------------------------------------------------------

# extracts a given dot-based variable e.g. '.general.environment' from the mss config JSON or TOML file
extract_env_var () {
  local env_name="$1";
  local res;
  res=$(printf '%s' "$__MSS_CONFIG_JSON__" | yq "$env_name");

  if [ -z "$res" ]; then
    _exit_with_error "Config Error: Use ${env_name}=<value> in the $MSS_CONFIG_FILE file.";
  fi
  
  echo "$res";
}

set_sigterm_handler()
{
    unset child_pid
    unset term_needed
    trap 'handle_sigterm' TERM INT
}

handle_sigterm()
{
  if [ "${child_pid}" ]; then
    kill -TERM "${child_pid}" 2>/dev/null;
  else
    term_needed="yes";
  fi
}

wait_for_process()
{
  child_pid=$1
  if [ "${term_needed}" ]; then
    kill -TERM "${child_pid}" 2>/dev/null
  fi

  wait "${child_pid}" 2>/dev/null
  trap - TERM INT
  wait "${child_pid}" 2>/dev/null
}

# port handling
PORT_NUMBER="${MSS_PORT:-$(extract_env_var ".general.mss_port")}"
[[ ! "$PORT_NUMBER" =~ ^[0-9]+$ ]]  &&  _exit_with_error "Port configuration failed. Use mss_port=<int> in the $MSS_CONFIG_FILE file."

# app settings
APP_SETTINGS=$(extract_env_var ".general.environment");

set_sigterm_handler

# puhuri sync
python -m api.scripts.puhuri_sync --ignore-if-disabled &
puhuri_script=$!

# rest-api
extra_args="";
if ! [ "$APP_SETTINGS" = "production" ]; then
  extra_args=" --reload";
fi

MSS_CONFIG_JSON_STR="$__MSS_CONFIG_JSON__" python -m uvicorn --host 0.0.0.0 --port "$PORT_NUMBER" api.rest:app --proxy-headers"$extra_args" &
uvicorn_script=$!

wait_for_process $puhuri_script
wait_for_process $uvicorn_script
