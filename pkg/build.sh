#!/bin/sh
# Builds build/mss, the folder the packages install as /usr/lib/tergite-mss, or
# /usr/local/lib/tergite-mss on macOS: uv's own build of Python, with the dependencies uv.lock
# pins and MSS's wheel installed into it, the dashboard's build, and the mss that runs them.
# The Python and some of the wheels are this machine's OS and architecture's, and ui/ must
# hold the dashboard's build first, as CONTRIBUTING.md describes: from the repo root,
# `pkg/build.sh`

set -e

version=${UV_PYTHON:-3.13}
out=build/mss
if [ "$(uname -s)" = Darwin ]; then
	installed_at=/usr/local/lib/tergite-mss
else
	installed_at=/usr/lib/tergite-mss
fi
[ -f ui/dist/index.html ] && [ ! -f ui/dist/dev-login.html ] || {
	echo "ui/dist has no dashboard, or npm run dev's stub: run npm ci and npm run build in ui/ first" >&2
	exit 1
}

rm -rf "$out" build/python build/wheel build/requirements.txt
mkdir -p "$out"

# uv's build of Python finds its own files from wherever it is, so it is copied whole, past the
# link of its minor version that uv adds beside it
UV_PYTHON_INSTALL_DIR="$PWD/build/python" uv python install --no-bin "$version"
python=$(UV_PYTHON_INSTALL_DIR="$PWD/build/python" uv python find --managed-python "$version")
cp -R "$(dirname "$(dirname "$(realpath "$python")")")" "$out/python"

uv export --frozen --no-dev --no-emit-project --no-hashes -o build/requirements.txt >/dev/null
# through the sdist, so that the wheel holds nothing a past build left in build/
uv build --out-dir build/wheel >/dev/null
uv pip install --python "$out/python/bin/python3" --break-system-packages --no-deps \
	--link-mode copy -r build/requirements.txt build/wheel/*.whl

# compiled here, as the installed folder is root's, with the paths it is installed at, so that
# a traceback shows the lines of its source
"$out/python/bin/python3" -m compileall -q -j 0 -s "$PWD/$out" -p "$installed_at" \
	"$PWD/$out/python/lib"

cp -R ui/dist "$out/dashboard"

cat >"$out/mss" <<'EOF'
#!/bin/sh
# runs MSS on the Python beside it, isolated from the caller's PYTHON* variables and working
# folder, serving the dashboard beside it unless MSS_DASHBOARD_DIR names another
here=$(dirname "$(realpath "$0")")
export MSS_DASHBOARD_DIR="${MSS_DASHBOARD_DIR:-$here/dashboard}"
exec "$here/python/bin/python3" -I -m main "$@"
EOF
chmod 0755 "$out/mss"
# MSS reads its config and key as it starts, even to print its help
MSS_CONFIG_FILE=tests/fixtures/config.test.toml PRIVATE_KEY_FILE=tests/fixtures/mss_private_key.pem \
	"$out/mss" --help >/dev/null
echo "$out"
