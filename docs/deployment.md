# Deployment

How to install and run MSS, with the dashboard, on a server. To run them from a checkout while
developing, follow the [README's quick start](../README.md#quick-start) instead.

MSS runs as a system service on port 8002, and serves the dashboard at `/ui`.

## Install from a release

1. Download the installer of a [release](https://github.com/tergite/tergite-frontend/releases):
   a deb for amd64 (Debian 13 and Ubuntu 24.04 onwards), or a macOS arm64 package.

2. Install it.
   - The deb asks where MSS's database is, or installs MongoDB or PostgreSQL beside it. It
     writes a production `/etc/tergite-mss/mss-config.toml` and a private key.
   - On macOS, copy the example config, and change the lines it marks `PRODUCTION`.

   ```shell
   # Debian or Ubuntu
   sudo apt install ./tergite-mss_<version>_amd64.deb

   # macOS
   sudo installer -pkg tergite-mss-<version>-macos-arm64.pkg -target /
   sudo cp /usr/local/share/tergite-mss/mss-config.example.toml /usr/local/etc/tergite-mss/mss-config.toml
   ```

3. Fill in the config:
   - `[[backends]]`, one per quantum backend; see [backends.md](backends.md);
   - `[auth]`'s login providers, with `cookie_domain` the host the dashboard is opened at;
     see [auth.md](auth.md);
   - `[email]`, the SMTP server.

4. Restart MSS.

   ```shell
   # Debian or Ubuntu; its log is in the journal: journalctl -u tergite-mss -f
   sudo systemctl restart tergite-mss

   # macOS; its log is /usr/local/var/log/tergite-mss.log
   sudo launchctl bootstrap system /Library/LaunchDaemons/se.chalmersnextlabs.tergite-mss.plist
   ```

5. Open [http://127.0.0.1:8002/ui](http://127.0.0.1:8002/ui) for the dashboard, and
   [http://127.0.0.1:8002/docs](http://127.0.0.1:8002/docs) for the API.

MSS answers `GET /health` with 200 for load balancers and probes; it is left out of the
access log.

## Run or install with uv

[uv](https://docs.astral.sh/uv/) can also run MSS from its repository, or install it as a
[tool](https://docs.astral.sh/uv/guides/tools/). Either way it runs in the foreground, not as a
service.

```shell
# once, without installing it
uvx --from git+https://github.com/tergite/tergite-frontend@v<version> mss start

# installed; `uv tool uninstall tergite-mss` removes it
uv tool install git+https://github.com/tergite/tergite-frontend@v<version>
MSS_DASHBOARD_DIR=/srv/tergite-mss/dashboard mss start
```

- It reads `mss-config.toml` and `private-mss-key.pem` in the folder it starts in, or the
  files `MSS_CONFIG_FILE` and `PRIVATE_KEY_FILE` name.
- It serves the API alone, unless `MSS_DASHBOARD_DIR` names the dashboard's build of the same
  release.

## The `mss` command

| Command | Does |
| --- | --- |
| `mss start` (the default) | migrates the database, then serves |
| `mss migrate` | migrates the database, MongoDB or SQL, and exits |
| `mss serve` | serves, without migrating |

`start` and `serve` take `--port` (default: the config's `general.mss_port`), `--host`,
`--forwarded-allow-ips`, `--workers` (default: `$WEB_CONCURRENCY`, or 1) and `--reload`.

A config encrypted with SOPS and a Hashicorp Vault key is decrypted by `start_mss.sh`, from a
checkout, with `VAULT_ADDR` and `VAULT_TOKEN` from the environment.

## Ship the logs to Grafana Loki

Install [Grafana Alloy](https://grafana.com/docs/alloy/latest/set-up/install/) beside MSS, with
this repository's [config.alloy](../config.alloy), which reads `tergite-mss.service`'s journal.
Set its environment, e.g. in `/etc/default/alloy` on Debian and Ubuntu:

```shell
CONFIG_FILE=/etc/alloy/config.alloy
ENVIRONMENT=production
GRAFANA_LOKI_URL=http://loki.example.com:3100/loki/api/v1/push
LOKI_LOGGER_ID=<some-id>
```

## What the packages contain

`pkg/build.sh` builds `build/mss`: uv's build of Python with the dependencies `uv.lock` pins
and MSS installed into it, the dashboard's build, and the `mss` script that runs them. The
deb and the macOS installer install that folder.

- The dashboard is built with the base `/ui/` and copied from `ui/dist` to
  `build/mss/dashboard`, which `mss` names in `MSS_DASHBOARD_DIR`. MSS serves it at `/ui`
  (`api/dashboard.py`), sends unknown paths to `index.html`, and redirects `/` to `/ui/`. The
  build calls the API on its own origin, so one build serves any MSS of its release.
- The wheel that `uv tool install` installs has no dashboard. `main.py` and `settings.py` are
  top-level modules, and the migrations a namespace package that `utils/migrations.py` points
  Alembic at. `tests/test_packaging.py` builds the wheel and runs it outside the checkout.

## Troubleshooting

**The service cannot be reached.** Check the firewall. To put MSS behind an nginx reverse
proxy on ports 80 and 443 (pointing at http://127.0.0.1:8002), open those ports:

```shell
sudo iptables -I INPUT -p tcp -m state --state NEW -m tcp -m multiport --dports 80,443 -j ACCEPT
```

Add `-s nnn.nnn.n.n/nn` to allow only a subnet, e.g. `-s 255.255.0.0/16`.

**Login succeeds, then bounces back to the login page.** `cookie_domain` in `[auth]` must be
the host you open the dashboard at. `localhost` and `127.0.0.1` are different hosts.
