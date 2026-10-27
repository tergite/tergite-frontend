#!/bin/sh
# Builds the standalone binary on a machine that is not Linux, in a container of the libc it
# targets, as Nuitka cannot cross-compile; on Linux, run its last two lines: from the repository root, `docker run --rm -e UV_PYTHON=3.13 -v "$PWD":/src -w /src ubuntu:24.04 pkg/build-linux.sh`
# for deb and rpm, or alpine for apk. Its glibc 2.39, as the release's, is the oldest the binary runs on.
# ui/ must hold the dashboard's build first, as CONTRIBUTING.md describes.

set -e

is_missing() {
	for tool in "$@"; do
		command -v "$tool" >/dev/null 2>&1 || return 0
	done
	return 1
}

# apt's packages and uv only where missing, as tergite/tergite-nuitka has them
if command -v apk >/dev/null 2>&1; then
	apk add --no-cache gcc musl-dev ccache curl
elif is_missing gcc patchelf ccache curl; then
	apt-get update -qq
	apt-get install -y -qq gcc patchelf ccache curl ca-certificates >/dev/null
fi
if is_missing uv; then
	curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
if command -v apk >/dev/null 2>&1; then
	# every Alpine has patchelf 0.18.0, which Nuitka refuses as a known-buggy release
	uv tool install patchelf==0.17.2.4
fi

uv sync --frozen --extra dev
uv run nuitka --assume-yes-for-downloads main.py
