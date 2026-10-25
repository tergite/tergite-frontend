#!/bin/sh
# Builds the onefile binary in a container of the libc it targets, Nuitka cannot cross-compile:
# from apps/tergite-mss, `docker run --rm -v "$PWD":/src -w /src debian:bookworm pkg/build-linux.sh`
# for deb and rpm, or alpine for apk. Bookworm's glibc 2.36 is the oldest the binary runs on.

set -e

if command -v apk >/dev/null 2>&1; then
	apk add --no-cache gcc musl-dev ccache curl
else
	apt-get update -qq
	apt-get install -y -qq gcc patchelf ccache curl ca-certificates >/dev/null
fi
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
if command -v apk >/dev/null 2>&1; then
	# every Alpine has patchelf 0.18.0, which Nuitka refuses as a known-buggy release
	uv tool install patchelf==0.17.2.4
fi

uv sync --extra dev
uv run nuitka --assume-yes-for-downloads main.py
