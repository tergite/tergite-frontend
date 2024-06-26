# Tergite WebGUI

![CI](https://github.com/tergite/tergite-frontend/actions/workflows/webgui-ci.yml/badge.svg)

The dashboard in the [Tergite software stack](https://tergite.github.io/) of the WACQT quantum computer.

**This project is developed by a core group of collaborators.**    
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror. 

## Dependencies

-   [Nodejs +18.12](https://nodejs.org/)
-   [Nextjs 12.3.4](https://nextjs.org/)
-   [Tergite MSS](../tergite-mss)
-   [Tergite landing page](../tergite-landing-page/)

## Quick Start

-   Ensure you have [tergite MSS](../tergite-mss) running.
-   Ensure you have [tergite landing page](../tergite-landing-page/) running.
-   Ensure you have [Nodejs +18.12](https://nodejs.org/) installed.
-   Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend/apps/tergite-webgui
```

-   Install the dependencies

```shell
npm i -g pnpm
pnpm i
```

-   Copy the `.env` file to `.env.local` file and update the variables in `.env.local` to the appropriate ones

```shell
cp .env .env.local
```

_Note: `API_BASE_URL` is the URL to the running [tergite MSS](../tergite-mss)_
_Note: `LANDING_ENDPOINT` is the URL to the running [tergite landing page](../tergite-landing-page)_
_Note: `WEBGUI_ENDPOINT` is the URL where this application is to be accessed_

-   Copy the `mss-config.example.toml` file to `mss-config.toml` file and update the variables in `mss-config.toml`
    that are the same as those in the `mss-config.toml` of the running [tergite MSS](../tergite-mss)

```shell
cp mss-config.example.toml mss-config.toml
```

_You can check the [MSS auth docs](../tergite-mss/docs/auth.md) for guidance_

-   Run the app in development mode

```shell
pnpm run dev
```

-   Open your browser at [http://127.0.0.1:3000](http://127.0.0.1:3000)

## Contribution Guidelines

If you would like to contribute to tergite-webgui, please have a look at our
[contribution guidelines](./CONTRIBUTING.md)

## Authors

This project is a work of
[many contributors](https://github.com/tergite/tergite-frontend/graphs/contributors).

Special credit goes to the authors of this project as seen in the [CREDITS](./CREDITS.md) file.

## ChangeLog

To view the changelog for each version, have a look at
the [CHANGELOG.md](./CHANGELOG.md) file.

## License

[Apache 2.0 License](./LICENSE)

## Acknowledgements

This project was sponsored by:

-   [Knut and Alice Wallenburg Foundation](https://kaw.wallenberg.org/en) under the [Wallenberg Center for Quantum Technology (WAQCT)](https://www.chalmers.se/en/centres/wacqt/) project at [Chalmers University of Technology](https://www.chalmers.se)
-   [Nordic e-Infrastructure Collaboration (NeIC)](https://neic.no) and [NordForsk](https://www.nordforsk.org/sv) under the [NordIQuEst](https://neic.no/nordiquest/) project
-   [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQ](https://cordis.europa.eu/project/id/820363) project
-   [European Union's Horizon Europe](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en) under the [OpenSuperQPlus](https://opensuperqplus.eu/) project

