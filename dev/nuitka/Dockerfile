# The image MSS and the backend build their Nuitka binaries in, with what their pkg/build-linux.sh
# install, uv's Python 3.13 and Node for the dashboard; Ubuntu 24.04, as its glibc 2.39 is the
# oldest the binaries then run on. From the repository root:
# `docker build --platform linux/amd64 -t tergite/tergite-nuitka:v2026.10.0 dev/nuitka`
FROM ubuntu:24.04

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /usr/local/bin/
COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/
COPY --from=node:20-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN apt-get update -qq \
  # make, for Nuitka's parallel LTO linking
  && apt-get install -y -qq gcc g++ make patchelf ccache curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
  && uv python install 3.13
