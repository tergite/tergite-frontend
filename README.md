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

## Dependencies

- [docker +v23.0.5](https://www.docker.com/products/docker-desktop/)
- [docker compose](https://docs.docker.com/compose/)
- Linux OS if the `LOGGING_DRIVER` variable in `.env` is set to 'journald' (**recommended**) since [journald is only for Linux](https://forums.docker.com/t/docker-for-windows-logging-failed-to-initialize-logging-driver-journald-is-not-enabled-on-this-host/68690/4).  
  _One could use the default `json-file` logging driver but this would quickly fill up one's disk space after some time. See [here](https://docs.docker.com/config/containers/logging/configure/)_.  
  _One could also use the `local` logging driver but external tools like promtail, our logging aggregator client, cannot work with it. See [here](https://docs.docker.com/config/containers/logging/local/)_

## Getting Started

- Ensure you have [docker](https://docs.docker.com/engine/install/) installed.

- Clone the repo

```shell
git clone git@github.com:tergite/tergite-frontend.git
```

- You might need to login to a hosted docker container registry e.g. one based on the [tergite-registry repo](https://github.com/tergite/tergite-registry),
  especially if you are going to use prebuilt tergite images.

```shell
# e.g. if container registry is hosted at example.com:8002
# and username is johndoe
# and password is password123
CONTAINER_REGISTRY=example.com:8002
DOCKER_USERNAME=johndoe
# feed in password when prompted
docker login ${CONTAINER_REGISTRY} -u $DOCKER_USERNAME
```

- Copy the `mss-config.example.toml` to `mss-config.toml` and update the configuration there.

```shell
cd tergite-frontend
cp mss-config.example.toml mss-config.toml
```

- Create a `.env` file basing on the `.env.example` file.
  Update the variables therein appropriately.

```shell
cp .env.example .env
```

- To rebuild and run the services, use the `fresh-docker-compose.yml`

```shell
docker compose -f fresh-docker-compose.yml up -d
```

- To use prebuilt images to run the services, use the `prebuilt-docker-compose.yml`

```shell
docker compose -f prebuilt-docker-compose.yml up -d
```

- Open your browser at

  - [http://localhost:8002](http://localhost:8002) to see the MSS service
  - [http://localhost:3000](http://localhost:3000) to see the dashboard application

- To ensure that the services start up even on server restarts, run:

```shell
sudo systemctl enable docker
```

- To stop the services, run:

```shell
docker compose -f fresh-docker-compose.yml stop
```

or for prebuilt:

```shell
docker compose -f prebuilt-docker-compose.yml stop
```

- To remove stop the services and remove their containers also, run:

```shell
docker compose -f fresh-docker-compose.yml down
```

or for prebuilt:

```shell
docker compose -f prebuilt-docker-compose.yml down
```

## How to Run wi

## FAQ

### Why can't I access the service?

It could be an issue with your iptables. Check them.

- You could set qal9000 behind an nginx reverse proxy pointing ports 80,443 to the landing page URL (http://localhost:8030), but don't forget to open up your firewall to allow connections on 80,443 ports

```shell
sudo iptables -I INPUT -p tcp -m state --state NEW -m tcp -m multiport --dports 80,443 -j ACCEPT
```

You could add `-s nnn.nnn.n.n/nn ` arg to the above command to limit access to only a given subnet e.g. `-s 255.255.0.0/16`

### Why aren't rules set in ufw working?

When docker is installed, it adds its own `iptables` rules which open all ports by default to the entire world. See [this article](https://docs.docker.com/network/packet-filtering-firewalls/) for more information. In order to customize these rules, new rules have to be added to the DOCKER-USER chain.

You can add other rules in the same DOCKER-USER chain, carefully :-)

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

- [ ] Make the 'Project External ID' input an autocomplete
    - Maybe add a read-only autocomplete GET endpoint for project IDs
    - Make the input autocomplete with shadcn `Combobox`
    - BLOCKED: RFC 0001 §4 makes this an explicit non-goal — "No autocomplete, search, or
      project browser for shared projects. Deliberate: project membership is not public" —
      and §8.3 repeats the refusal. Any endpoint listing project IDs lets any logged-in user
      enumerate every project in the system. Needs a decision to amend the RFC before it can
      be built; the admin-only email autocomplete below is not in tension and can proceed.
- [ ] After approving a project access request, there is a `Failed to fetch` error:
      ```
      Access to fetch at 'http://127.0.0.1:8002/admin/user-requests/6a8c3bac0c6f8beedba1ad33' from origin 'http://127.0.0.1:3000' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource.
      TypeError: Failed to fetch
      at ht (index-74TWp7kT.js:288:81530)
      at Object.U7 [as mutationFn] (index-74TWp7kT.js:288:75145)
      at Object.fn (index-74TWp7kT.js:288:42969)
      at C (index-74TWp7kT.js:288:33357)
      at Object.start (index-74TWp7kT.js:288:33816)
      at JA.execute (index-74TWp7kT.js:288:43774)
  fw	@	index-74TWp7kT.js:40
      ```
    - Probably use similar layout in the admin pages to that used in the dashboard pages
- [ ] Health check requests spam the logs for all apps (MSS, Dashboard, backend)
    - Options:
      - Add a healthcheck endpoint which shows no logs (e.g. the logs to it are filtered out by the server software)? 
      - Reduce information passed in INFO logs. Only ERROR, WARNING and DEBUG probably need such detail of information
- [ ] When a project is created or updated with a given admin, the admin is never notified
      - Add a notification for the user who is made admin
- [ ] When a project is created or updated with a new user or an old user is removed, the given user is not notified
      - Add a notification for all users old and new ensuring that those who have lost access are told so, while those who have been given access
        they didnot have are also notified
- [ ] In project creation and project update forms, make 'Admin email' and 'Member emails' inputs autocomplete for admins
      - Add an admin only autocomplete emails endpoint on MSS
      - Use shadcn's Combobox for those two inputs
- [ ] When Project access requests or QPU time requests are approved or rejected directly and not in the notifications dropdown, the notifications remain intact
      and must be marked 'read' manually.
      - Automatically mark notifications associated with a given user request as read for all approving/rejecting users
- Handle 503 unavailbale service on the dashboard
- Handle the disconnection issues between MSS and the backends

## Acknowledgements

This project was sponsored by:

- [Knut and Alice Wallenberg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WACQT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
- [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
- [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project
