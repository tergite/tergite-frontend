# tergite-frontend

[![Frontend CI](https://github.com/tergite/tergite-frontend/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/frontend-ci.yml)

The Frontend in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

![Login screen](./apps/tergite-dashboard/docs/assets/login-screen.png)
The login screen

![Home screen](./apps/tergite-dashboard/docs/assets/home-screen.png)
The home screen

![Tergite dashboard showcase](./apps/tergite-dashboard/docs/assets/dashboard-showcase.gif)
A preview of the the dashboard

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Services

- [Tergite Dashboard](./apps/tergite-dashboard/) [![Dashboard CI](https://github.com/tergite/tergite-frontend/actions/workflows/dashboard-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/dashboard-ci.yml)  
  The website that shows the state of the quantum computer
- [Tergite Main Service Server or MSS](./apps/tergite-mss/) [![MSS CI](https://github.com/tergite/tergite-frontend/actions/workflows/mss-ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/mss-ci.yml)  
  The server that controls all services on this frontend.  
  It also exposes the REST API through which other clients like [tergite SDK](https://github.com/tergite/tergite) communicate with the quantum computers.

## Deployment

MSS runs from its package, as a system service, and serves the dashboard. MongoDB, or
PostgreSQL, and Redis are expected to be installed already, or are installed alongside MSS on
Debian and Ubuntu.

### MSS

- Download the installer of a [release](https://github.com/tergite/tergite-frontend/releases):
  a deb for amd64, for Debian 13 and Ubuntu 24.04 onwards, or a macOS arm64 installer.

- On Debian or Ubuntu, install the deb. It asks where MSS's database and Redis are, creates
  their accounts, writes `/etc/tergite-mss/mss-config.toml` with a private key beside it, and
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

[Apache 2.0 License](./LICENSE)

## TODO

- [ ] Notifications marked as read still show up in the notification list.
    - they should disappear after being marked read
- [ ] Make the 'Project External ID' input an autocomplete
    - Maybe add a read-only autocomplete GET endpoint for project IDs
    - Make the input autocomplete with shadcn `Combobox`
    - Decided: logged-in users may see the shared projects; they are not PII, and joining
      one still needs its admin's approval.
- [ ] Health check requests spam the logs of tergite-backend
    - MSS and the dashboard now answer the container probe on an unlogged `/health`; the
      backend lives in its own repo and needs the same treatment there.
- Handle 503 unavailbale service on the dashboard
- Handle the disconnection issues between MSS and the backends
    - NEEDS A DECISION, not just a patch. `is_online` is set True on websocket connect and
      False only in the `WebSocketDisconnect` handler
      (`api/rest/routers/devices/__init__.py`), so a backend that dies without closing
      cleanly stays "online" until TCP notices. Two candidate fixes, neither safe to land
      unreviewed:
      - **Liveness TTL in MSS alone.** Stamp `last_seen` on every websocket frame and treat
        a device whose stamp is older than N as offline when serving it. No backend change,
        but it redefines `is_online` for every consumer — dashboard, fixtures, e2e — and a
        quiet-but-healthy backend would read as offline unless it is made to send keepalives.
      - **Websocket ping/pong with a deadline**, which is the real answer but needs a matching
        change in tergite-backend and therefore an RFC spanning both repos.
        <!-- FIXME: Choose this. Note however that the disconnection issues would not have been solved.
        In the past, the backend abruptly became unreachable in production and sometimes even the 
        frontend did the same. I was thinking of having a stream-persisted NATS in between them
        at least as another medium of exchange between the two - being switchable say in one of 
        our config files such that if one wants to use websockets, they go ahead. If NATS they go ahead.
        It would also mean it is easy to check if the NATS gets rid of those sporadic disconnections.
        But all this is for a future RFC or something-->

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
- [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
