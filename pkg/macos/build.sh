#!/bin/sh
# Packages build/mss, which pkg/build.sh builds, as a macOS installer: run from the repository
# root with VERSION set, e.g. `VERSION=2026.10.0 pkg/macos/build.sh`. SIGN_IDENTITY, a "Developer ID
# Installer" certificate's name, signs it; without one Gatekeeper blocks the installer.

set -e

[ -n "$VERSION" ] || {
	echo "VERSION is not set" >&2
	exit 1
}

label=se.chalmersnextlabs.tergite-mss
arch=$(uname -m)
output=dist/tergite-mss-$VERSION-macos-$arch.pkg
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT

install -d "$root/usr/local/bin" "$root/usr/local/lib" "$root/usr/local/share/tergite-mss" \
	"$root/Library/LaunchDaemons"
# uv's Python with MSS installed into it, the dashboard, and the mss that runs them, which
# finds the folder through the link
cp -R build/mss "$root/usr/local/lib/tergite-mss"
ln -s ../lib/tergite-mss/mss "$root/usr/local/bin/tergite-mss"
install -m 0644 mss-config.example.toml "$root/usr/local/share/tergite-mss/"
install -m 0755 pkg/macos/uninstall.sh "$root/usr/local/share/tergite-mss/"
install -m 0644 "pkg/macos/$label.plist" "$root/Library/LaunchDaemons/"
# extended attributes, like a download's quarantine, ship as ._ entries that Installer
# reapplies; com.apple.provenance cannot be removed and stays
xattr -cr "$root"

mkdir -p dist
pkgbuild --root "$root" \
	--scripts pkg/macos/scripts \
	--identifier "$label" \
	--version "$VERSION" \
	--ownership recommended \
	${SIGN_IDENTITY:+--sign "$SIGN_IDENTITY"} \
	"$output"
echo "$output"
