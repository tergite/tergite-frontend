# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format {year}.{month}.{patch_number}.

## CHANGELOGs for Constituent Apps

Please refer to the `CHANGELOG.md` file of the app in question.

- [./apps/tergite-dashboard/CHANGELOG.md](./apps/tergite-dashboard/CHANGELOG.md)
- [./apps/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md)

## [unreleased]

- Add external loki logger support for promtail for linux

## [2025.06.2] - 2025-06-17

### Fixed

- Fix silent errors in e2e tests on Github during cleanup

## [2025.06.1] - 2025-06-16

### Fixed

- Fix failing e2e tests on Github during cleanup

## [2025.06.0] - 2025-06-16

### Changed

- BREAKING: Removed v2 from MSS URL in env and docker configs

More changes in [apss/tergite-dashboard/CHANGELOG.md](./apps/tergite-dashboard/CHANGELOG.md#2025060---2025-06-16)
More changes in [apss/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md#2025060---2025-06-16)

## [2025.03.1] - 2025-03-18

### Changed

- Changed the backend configurations for the full e2e to run with the new backend configuration files

More changes in [apss/tergite-dashboard/CHANGELOG.md](./apps/tergite-dashboard/CHANGELOG.md#2025031---2025-03-18)
More changes in [apss/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md#2025031---2025-03-18)

## [2025.03.0] - 2025-03-14

More changes in [apss/tergite-dashboard/CHANGELOG.md](./apps/tergite-dashboard/CHANGELOG.md#2025030---2025-03-14)
More changes in [apss/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md#2025030---2025-03-14)

### Added

- Added Full end-to-end testing combining the backend, API and dashboard

## [2024.12.2] - 2025-01-22

See [apss/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md#2024122---2025-01-22)

## [2024.12.1] - 2024-12-20

### Changed

- Updated the Github actions to push the ':latest' tag along side the version tag to docker registry
- Updated `prebuilt-docker-compose.yml` to pick relevant values from the environment as well as
  from `mss-config.toml` for the dashboard docker compose service

### Fixed

- Fixed the 'parent-folder' image not found error in the Github actions for the dashboard

## [2024.12.0] - 2024-12-11

### Added

- Added the admin pages for managing user access in the tergite-dashboard app. See more in [./apps/tergite-dashboard/CHANGELOG.md](./apps/tergite-dashboard/CHANGELOG.md#2024120---2024-12-11)
- Added user access endpoints to the v2 API version of the tergite-mss app. See more in [./apps/tergite-mss/CHANGELOG.md](./apps/tergite-mss/CHANGELOG.md#2024120---2024-12-11)
- Added the `MSS_PORT` environment variable to the `.env.example` to configure the port on which tergite-mss runs on in docker compose.
- Added the `NETWORK_MODE` environment variable to the `.env.example` to configure the `network_mode` to use in docker compose file

## [2024.09.0] - 2024-09-02

### Added

- Added the tergite-dashboard app

### Changed

- Removed the tergite-landing-page app
- Removed the tergite-webgui app

### Fixed

## [2024.04.1] - 2024-05-28

### Added

### Changed

- Updated the contribution guidelines and government model statements

### Fixed

## [2024.04.0] - 2024-04-16

### Added

- Added the [tergite-landing-page constituent app](./apps/tergite-landing-page/)
- Added the [tergite-mss constituent app](./apps/tergite-mss/)
- Added the [tergite-webgui constituent app](./apps/tergite-webgui/)
- Added github actions for all constituent apps
- Added the docker compose [`./prebuilt-docker-compose.yml`](./prebuilt-docker-compose.yml) for pre-built image
- Added the docker compose file [`./fresh-docker-compose.yml`](./fresh-docker-compose.yml) for cases when the constituent apps have to be built on the fly.

### Changed

- Updated the README.md

### Fixed
