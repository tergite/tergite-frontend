# tergite-frontend

[![CI](https://github.com/tergite/tergite-frontend/actions/workflows/ci.yml/badge.svg)](https://github.com/tergite/tergite-frontend/actions/workflows/ci.yml)

The Frontend in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer:
the Main Service Server (MSS), the API through which users reach the quantum computers, and the
dashboard, the website that shows their state.

**This project is developed by a core group of collaborators.**
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

![Login screen](./ui/docs/assets/login-screen.png)
The login screen

![Home screen](./ui/docs/assets/home-screen.png)
The home screen

![Tergite dashboard showcase](./ui/docs/assets/dashboard-showcase.gif)
A preview of the the dashboard

## Quick Start

Run MSS and the dashboard on your machine, with test data and no other services. You need
[uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js 26.12.1 or later](https://nodejs.org/).

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
uv sync --extra dev
cp mss-config.example.toml mss-config.toml
openssl genpkey -algorithm RSA -out private-mss-key.pem -pkeyopt rsa_keygen_bits:4096
cd ui
npm i
npm run dev
```

Then open [http://127.0.0.1:5173/ui/](http://127.0.0.1:5173/ui/), click **Log in as a seeded
user** and pick one: `jane.doe@example.com` is an admin, `john.doe@example.com` a plain user.

## Documentation

| Document | Read it to |
| --- | --- |
| [docs/deployment.md](./docs/deployment.md) | install MSS and the dashboard on a server, run them with uv, ship their logs |
| [docs/auth.md](./docs/auth.md) | set up login providers, and understand users, projects and app tokens |
| [docs/backends.md](./docs/backends.md) | connect a quantum backend to MSS |
| [DESIGN.md](./DESIGN.md) | understand how MSS and the dashboard are built, before changing them |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | run the tests, build the packages and follow the code conventions |
| [docs/](./docs) | dig into storage and the REST API's conventions |

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

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
