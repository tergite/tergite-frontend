# tergite-landing-page

![CI](https://github.com/tergite/tergite-frontend/actions/workflows/landing-page-ci.yml/badge.svg)

The landing page in the [Tergite software stack](https://tergite.github.io/) of the Swedish Quantum computer.

**This project is developed by a core group of collaborators.**    
**Chalmers Next Labs AB (CNL) takes on the role of managing and maintaining this project.**

## Version Control

The tergite stack is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror. 

## Dependencies

-   [nodejs +v18.16.0](https://nodejs.org/en/download)
-   [nextjs +v13.4.19](https://nextjs.org/)

## Getting Started

-   Ensure you have [nodejs +v18.16.0](https://nodejs.org/en/download) installed

-   Clone the repo

```shell
git clone git@github.com:tergite/tergite-frontend.git
```

-   Install dependencies

```shell
cd tergite-frontend/apps/tergite-landing-page
npm install
```

-   Copy the `mss-config.example.toml` to `mss-config.toml` and update the configuration there.  
    Make sure it is the same being used by the [tergite-mss](../tergite-mss/) instance connected to this app

```shell
cp mss-config.example.toml mss-config.toml
```

-   To update the environment variables, you also need to copy the `.env` file to `.env.local` and
    update the environment variables therein.

```shell
cp .env .env.local
```

-   Run the development server

```shell
npm run dev
```

-   Checkout the site at [http://localhost:3000](http://localhost:3000) in your browser

## Contribution Guidelines

If you would like to contribute to tergite-webgui, please have a look at our
[contribution guidelines](./CONTRIBUTING.md)

## Authors

This project is a work of [many contributors](https://github.com/tergite/tergite-frontend/graphs/contributors).

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

