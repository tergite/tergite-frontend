# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format `{year}.{month}.{patch_number}`.

## [Unreleased]

## [2026.03.0] - 2026-03-06

- No Change

## [2025.12.0] - 2026-03-16

### Fixed

- Fixed module 'fastapi_users.schemas' has no attribute 'model_validate'
- Fixed error 'redirect URI '.../auth/{client}/callback' specified in the request does not match the redirect URIs'

### Added

- Added the `/bookings/{backend}/config` endpoint to return the configuration for the booking service for given backend
- Added back the `/auth/app/{OATH_CLIENT}` URLs for backward compatibility
- Added filtering bookings at `/bookings/{backend}` endpoint by `user_id`
- Added sorting bookings at `/bookings/{backend}` endpoint by any field
- Added the "backend" property to the `BookingsConfig` and the `Booking` schemas returned to the client
- Added a way to load AppConfig config from a JSON string passed in `MSS_CONFIG_JSON_STR` env var
- Added decryption of mss config using sops
- Added the `private_key_password` in AppConfig containing the password used for encrypting private key PEM files
- [BREAKING]: Added the `redis_url` property under the database configuration
- [BREAKING]: Added the `public_key_path` property under the backend configuration
- [BREAKING]: Added the `/devices/ws/{name}` endpoint for handling device events e.g. 'initialized', 'recalibrated', 'job_updated'
- Added `public_url` property on BCC config, just in case the public URL for a backend is different from the private one
- Added `request_log_ttl` and `request_log_clean_interval` to control the rate at which request logs are cleared
- Added TTL on `Collection` of the redis_store
- Added `pi_pulse_motzoi` parameter for qubit calibration

### Changed

- [BREAKING]: Removed the ability to load mss config toml file in python. One must use the `start_mss.sh` script.
- [BREAKING]: Changed backend connection to MSS to use RSA-secured websockets
- [BREAKING]: Removed the `/devices` and `/calibrations` POST and PUT endpoints
- [BREAKING]: Removed the `/jobs` PUT endpoint

## [2025.09.0] - 2025-10-02

### Added

- Added filtering bookings by minimum/maximum start timestamps
- Added username property to the Booking data structure

## [2025.09.0] - 2025-09-30

### Added

- Added `access_token` field to the job schema.
  It is encrypted when in database but plain when requested for by anyone who has access to the job
  (including other members of the project).
- Added the following endpoints for use in booking time slots
  - POST `/admin/bcc-users/{backend}` - for admins to create users in backends
  - GET `/admin/bcc-users/{backend}` - for admins to view users in backends
  - DELETE `/admin/bcc-users/{backend}/{user_id}` - for admins to remove users in backends
  - POST `/bookings/{backend}` - for users to create bookings in backends
  - POST `/bookings/{backend}/{booking_id}/cancel` - for users to cancel bookings in backends
  - GET `/bookings/{backend}` - for users to view bookings in backends

### Changed

- BREAKING: Changed the response to job creation `/jobs` POST endpoint, to return a JWT access token also
- BREAKING: Changed the authentication with BCC to use private key signed signatures in headers
- BREAKING: Removed the option to disable authentication as it is a requirement for BCC

## [2025.06.2] - 2025-06-17

- No change

## [2025.06.1] - 2025-06-16

- No change

## [2025.06.0] - 2025-06-16

### Changed

- BREAKING: Replaced `requirements.txt` with `pyproject.toml`
- BREAKING: Upgraded lowest version of python supported to python 3.12
- BREAKING: Upgraded Fastapi to 0.115.12
- BREAKING: Upgraded pydantic to the latest v2
- BREAKING: Removed the v1/auth, v1/backends and v1/jobs endpoints
- BREAKING: Changed creation of jobs to require a body with required fields 'device' and 'calibration_date'
- BREAKING: Disabled Mongo-style payloads when updating jobs to ensure more security by reducing capabilities exposed to HTTP
- BREAKING: Changed job update payloads to only accept the fields that are in the Job schema
- BREAKING: Changed the POST `/v2/calibrations` endpoint to receive only a single calibration result at a time
- BREAKING: Changed the GET `/v2/calibrations/` endpoint to return a paginated response of calibrations
- BREAKING: Made 'calibration_date' a required property on the job object
- BREAKING: Changed the GET `/v2/me/jobs` endpoint to `/me/jobs/`
- BREAKING: Changed the GET `/me/jobs` endpoint to return a paginated response of jobs
- BREAKING: Changed `/v2/` endpoints to `/` endpoints
- BREAKING: Remove version property from project schema
- BREAKING: Return paginated response on the GET `/devices/` endpoint
- BREAKING: Return paginated response on the GET `/auth/providers/` endpoint
- BREAKING: Change the query param 'domain' on the GET `/auth/providers/` endpoint to 'email_domain'

### Added

- Added more extensive search capability on the GET `/jobs/` endpoints so that one can search by more fields in the job
- Added more extensive search capability on the GET `/devices/` endpoints so that one can search by more fields in the devices
- Added more extensive search capability on the GET `/calibrations/` endpoints so that one can search by more fields in the calibrations
- Added more extensive search capability on the GET `/auth/providers/` endpoints so that one can search by more fields in the auth providers

## [2025.03.1] - 2025-03-18

No change

## [2025.03.0] - 2025-03-14

### Changed

- Renamed `quantum_jobs` to `jobs` service
- Removed the api routes, DTOs and service methods for the old WebGUI project.

## [2024.12.2] - 2025-01-22

### Changed

- Raise logging level to WARN when app settings are not production
- Remove NETWORK_MODE environment variable

### Fixed

- Fix auth openid errors when auth is disabled

## [2024.12.1] - 2024-12-20

No change

## [2024.12.0] - 2024-12-11

### Added

- Added GET `/v2/me` endpoint to get current user info
- Added DELETE `/v2/me/projects/{id}` endpoint to delete project current user administers
- Added GET `/v2/admin/qpu-time-requests` endpoint to get all user requests to increase QPU seconds on a project
- Added POST `/v2/admin/qpu-time-requests` endpoint for project members to request for more QPU seconds
- Added GET `/v2/admin/user-requests` endpoint for admins to retrieve a list of user requests
- Added PUT `/v2/admin/user-requests/{id}` endpoint for admins to update (e.g. approve/reject) as user request
- Added POST `/v2/admin/projects/` endpoint for admins to create a new project
  - Creates new empty user if non-existent emails are passed as user_emails or admin_email
- Added GET `/v2/admin/projects/` endpoint for admins to retireve a list of projects
- Added GET `/v2/admin/projects/{id}` endpoint for admins to view a project of given id
- Added PUT `/v2/admin/projects/{id}` endpoint for admins to update a project of given id
  - Creates new empty user if non-existent emails are passed as user_emails or admin_email
- Added DELETE `/v2/admin/projects/{id}` endpoint for admins to soft delete a project
- Added the PUT `/auth/me/app-tokens/{token_id}` endpoint for extending app token's lifetimes
- Added the PUT `/v2/me/tokens/{token_id}` endpoint for extending app token's lifetimes

### Fixed

- Fixed the not found error when deleting expired app tokens
- Fixed httpx version to 0.27.2 as 0.28.0 removes many deprecations that we were still dependent on in FastAPI testClient

## [2024.09.1] - 2024-09-24

### Added

- Added example scopes in the mss_config.example.toml
- Added units 'Hz' and 's' to calibration data schema

### Fixed

- Fixed CORS error when dashboard and MSS are on different domains or subdomains
- Fixed 'AttributeError: 'NoneType' object has no attribute 'resource_usage'' on GET /v2/me/jobs

### Changed

- Removed `archives` folder
- Removed `dev` folder
- Changed all calibration v2 properties optional

## [2024.09.0] - 2024-09-02

### Added

- Added v2 endpoints including
  - `/v2/me/projects/` to `GET`, `POST` current cookie user's projects
  - `/v2/me/projects/{project_id}` to `GET`, `PUT` current cookie user's single project
  - `/v2/me/tokens/` to `GET`, `POST` current cookie user's application tokens
  - `/v2/me/tokens/{token_id}` to `GET`, `PUT` current cookie user's application token
  - `/v2/me/jobs/` to `GET` current cookie user's jobs (with option of specifying project id)
  - `/v2/auth/providers` to `GET` the available Oauth2 provider corresponding to a given email domain
  - `/v2/auth/{provider}/authorize` to `POST` Oauth2 initialization request for given `provider`
  - `/v2/auth/{provider}/callback` to handle `GET` redirects from 3rd party Oauth2 providers after successful login
  - `/v2/auth/logout` to handle `POST` requests to logout the current user via cookies
  - `/v2/calibrations/` to `GET`, `POST` calibration data for all devices. `POST` is available for only system users.
  - `/v2/calibration/{device_name}` to `GET` calibration data for the device of the given `device_name`
  - `/v2/devices` to `GET`, `PUT` (upsert) all devices. `PUT` is available for only system users.
  - `/v2/devices/{name}` to `GET`, `PUT` the device of a given name. `PUT` is available for only system users.

## [2024.04.1] - 2024-05-28

### Added

- Added ability to handle multiple Tergite backends

### Changed

- Updated the contributions guidelines and the government model

### Fixed

## [2024.04.0] - 2024-04-16

### Added

### Changed

- Moved tergite-mss to the tergite-frontend monorepo
- Changed configuration control to use `mss-config.toml` not `.env`
- Removed the `auth_config.toml` file

### Fixed

## [2024.02.0] - 2024-03-07

This is part of the tergite release v2024.02 that introduces authentication, authorization and accounting to the
tergite stack

### Added

- Added authentication via JWT tokens in cookies
- Added authentication via JWT tokens in Authorization header
- Added role-based authorization via JWT tokens
- Added project-based authorization via app tokens saved in the database
- Added project-based tracking of QPU usage in terms of durations of experiments
- Integrated [Puhuri HPC/cloud allocation service](https://puhuri.io/)

### Changed

### Fixed

## [2023.12.0] - 2024-03-06

This is part of the tergite release v2023.12.0 that is the last to support [Labber](https://www.keysight.com/us/en/products/software/application-sw/labber-software.html).
Labber is being deprecated.

### Added

- Initial release of the tergite-mss server
- Added support for the [WebGUI](https://github.com/tergite/tergite-webgui)

### Changed

### Fixed
