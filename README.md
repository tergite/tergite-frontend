# tergite-frontend

[![CI](https://github.com/tergite/tergite-frontend/actions/workflows/ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/ci.yml)

The Frontend in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer:
the Main Service Server (MSS), the public API through which clients like the
[tergite SDK](https://github.com/tergite/tergite) reach the quantum computers, and the dashboard it
serves, the website that shows their state.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

![Login screen](./ui/docs/assets/login-screen.png)
The login screen

![Home screen](./ui/docs/assets/home-screen.png)
The home screen

![Tergite dashboard showcase](./ui/docs/assets/dashboard-showcase.gif)
A preview of the the dashboard

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Layout

This folder is MSS, a FastAPI app; the dashboard, a React app, is in [ui/](./ui), and MSS serves
its build at `/ui`. [DESIGN.md](./DESIGN.md) describes how they are built, and [docs/](./docs)
more of MSS's API.

## Deployment

MSS runs from its package, as a system service, and serves the dashboard. MongoDB or
PostgreSQL is expected to be installed already, or is installed alongside MSS on Debian and
Ubuntu.

### MSS

- Download the installer of a [release](https://github.com/tergite/tergite-frontend/releases):
  a deb for amd64, for Debian 13 and Ubuntu 24.04 onwards, or a macOS arm64 installer.

- On Debian or Ubuntu, install the deb. It asks where MSS's database is, creates its
  account, writes `/etc/tergite-mss/mss-config.toml` with a private key beside it, and
  starts the `tergite-mss` service on port 8002.

```shell
sudo apt install ./tergite-mss_<version>_amd64.deb
```

- Fill in the rest of `/etc/tergite-mss/mss-config.toml`: its backends, the `[auth]` OpenID
  clients and cookie settings, and the `[email]` SMTP server; then restart MSS. Its log is in
  the journal.

```shell
sudo systemctl restart tergite-mss
journalctl -u tergite-mss -f
```

- On macOS, install the package, write `/usr/local/etc/tergite-mss/mss-config.toml` from the
  example it installs, then start the service. Its log is `/usr/local/var/log/tergite-mss.log`.

```shell
sudo installer -pkg tergite-mss-<version>-macos-arm64.pkg -target /
sudo cp /usr/local/share/tergite-mss/mss-config.example.toml /usr/local/etc/tergite-mss/mss-config.toml
sudo launchctl bootstrap system /Library/LaunchDaemons/se.chalmersnextlabs.tergite-mss.plist
```

- Open [http://localhost:8002/docs](http://localhost:8002/docs) to see MSS's API.

### Dashboard

MSS serves the dashboard at `/ui`, to which `/` redirects: open
[http://localhost:8002/ui](http://localhost:8002/ui). The `cookie_domain` of `[auth]` in MSS's
config must be the host you open it at.

MSS serves the build it ships with; `MSS_DASHBOARD_DIR` may name another folder holding the
dashboard's build of the same release, and MSS fails to start when that folder does not exist.

### Run or install with uv

MSS is the package's `mss` command, so [uv](https://docs.astral.sh/uv/) also runs it from its
repository without installing it, or installs it as a [tool](https://docs.astral.sh/uv/guides/tools/)
on the `PATH`, with the Python 3.13 it needs. A tool runs where it is started rather than as a
service, and comes without the dashboard: give it the dashboard's build of the same release in
`MSS_DASHBOARD_DIR`, or it serves its API alone.

- Once, without installing it:

```shell
uvx --from git+https://github.com/tergite/tergite-frontend@v<version> mss start
```

- Installed as a tool; to change version, install the other tag with `--force`, and
  `uv tool uninstall tergite-mss` removes it:

```shell
uv tool install git+https://github.com/tergite/tergite-frontend@v<version>
MSS_DASHBOARD_DIR=/srv/tergite-mss/dashboard mss start
```

It reads `mss-config.toml` and `private-mss-key.pem` in the folder it starts in, or the files
`MSS_CONFIG_FILE` and `PRIVATE_KEY_FILE` name; a backend's relative `public_key_path` is in that
folder too. From a checkout, `uv run mss start` runs it as `./start_mss.sh` does, but without
decrypting a SOPS-encrypted config.

### Logs

To ship MSS's journal to Grafana Loki, install [Grafana Alloy](https://grafana.com/docs/alloy/latest/set-up/install/)
beside it with this repository's [config.alloy](./config.alloy), and set its environment, e.g. in
`/etc/default/alloy` on Debian and Ubuntu:

```shell
CONFIG_FILE=/etc/alloy/config.alloy
ENVIRONMENT=production
GRAFANA_LOKI_URL=http://loki.example.com:3100/loki/api/v1/push
LOKI_LOGGER_ID=<some-id>
```

## Development

- Ensure you have [uv](https://docs.astral.sh/uv/getting-started/installation/) installed,
  [Node.js 26.12.1 or later](https://nodejs.org/) for the dashboard, and a
  [tergite backend](https://github.com/tergite/tergite-backend) running.
- Clone the repo and install the dependencies, which uv puts in `.venv`, with Python 3.13 or
  later, as `uv.lock` pins them

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
uv sync --extra dev
```

- Copy the `mss-config.example.toml` file to `mss-config.toml` and update the variables there
  appropriately.

```shell
cp mss-config.example.toml mss-config.toml
```

- If you don't have a key pair for MSS, generate one, and copy the public key to the backend
  machine's tergite-backend folder. Take note of the password `PRIVATE_KEY_PASSWORD` you provide,
  or skip `-pass` to be prompted for one. `PRIVATE_KEY_FILE` may name another path for the
  private key.

```shell
openssl genpkey -algorithm RSA \
  -out private-mss-key.pem \
  -pkeyopt rsa_keygen_bits:4096 \
  -aes-256-cbc
openssl rsa -pubout -in private-mss-key.pem -out public-mss-key.pem
# scp public-mss-key.pem backend-host:~/tergite-backend/
```

- Run the start script, then open [http://localhost:8002/docs](http://localhost:8002/docs) to
  see the interactive API docs

```shell
uv run ./start_mss.sh
```

- To work on the dashboard, run it in development mode, against MSS: this seeds the database of
  MSS's config (`mss-config.toml`, or the file `MSS_CONFIG_FILE` names) with
  [ui/fixtures/](./ui/fixtures), clearing those tables, serves MSS on 8002 and runs vite against
  it at [http://127.0.0.1:5173/ui/](http://127.0.0.1:5173/ui/)

```shell
cd ui
npm i
npm run dev
```

## FAQ

### Why can't I access the service?

It could be an issue with your iptables. Check them.

- You could set qal9000 behind an nginx reverse proxy pointing ports 80,443 to the landing page URL (http://localhost:8030), but don't forget to open up your firewall to allow connections on 80,443 ports

```shell
sudo iptables -I INPUT -p tcp -m state --state NEW -m tcp -m multiport --dports 80,443 -j ACCEPT
```

You could add `-s nnn.nnn.n.n/nn ` arg to the above command to limit access to only a given subnet e.g. `-s 255.255.0.0/16`

## Contribution Guidelines

If you would like to contribute to tergite-frontend, please have a look at our [contribution guidelines](./CONTRIBUTING.md)

## Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-frontend/graphs/contributors).

Special credit goes to the authors of this project as seen in the [CREDITS](./CREDITS.md) file.

## ChangeLog

To view the changelog for each version, have a look at the [CHANGELOG.md](./CHANGELOG.md) file.

## License

[Apache 2.0 License](./LICENSE.txt)

## TODO

- [ ] Fix failing GitHub/GitLab CI runs

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
- [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
