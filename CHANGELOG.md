# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format `{year}.{month}.{patch_number}`.

Until the dashboard joined MSS, each kept a changelog of its own, and the repository one more;
their entries are merged here, the dashboard's marked `Dashboard:` and the repository's `Repository:`.

## [Unreleased]

### Added

- Added `MSS_DASHBOARD_DIR`, the folder of the dashboard's build MSS serves at `/ui`, where before
  MSS could only serve the build in `ui/dist` beside its code
- Added the `mss` command to the package, so `uv tool install` installs MSS from its repository with its
  migrations, where before only the deb and macOS installers ran it outside a checkout

### Changed

- Changed the default `mss-config.toml` and `private-mss-key.pem`, and a backend's relative `public_key_path`, to
  be read from the folder MSS starts in, where before they were read from beside MSS's code
- Repository: Changed MSS's linting from black, isort and pyflakes to ruff, which formats, sorts the imports and
  finds what pyflakes did; contributors run `ruff format` and `ruff check` where they ran the three
- Changed the devices, calibrations and jobs MSS keeps to hold only the fields their schemas declare, where before
  they also kept whatever else they were sent; a calibration's qubits and resonators now declare their `name`, and
  its couplers their `short_name`, `full_name`, `control_qubit` and `target_qubit`, which the backend sends

### Fixed

- Fixed MSS on PostgreSQL or SQLite never registering a backend's device, whose event carried fields MSS does not
  declare; MSS now reads each event as tergite-backend's OpenAPI spec declares it, dropping anything else

## [2026.11.0-rc.5] - 2026-11-04

### Changed

- Repository: Changed the e2e to run against the backend's newest release of the same minor where it has no branch or
  tag of this one's name, where before it ran against the backend's `main`

## [2026.11.0-rc.4] - 2026-11-04

### Added

- Added a project's `is_pulse_allowed`, which only a superuser sets, and which MSS sends the backend on asking
  for each job's token, so that the backend lets the project's pulse-level jobs in, within its own limits
- Added the `project-pulse-access` request, by which a project's member asks the superusers to allow its
  pulse-level jobs, with its `pulse-access-requested`, `-granted` and `-denied` notices
- Added a "Pulse-level jobs" column to the dashboard's projects page, from which a member asks for a project's
  pulse-level jobs, or sees that they are allowed
- Added a calibration's optional `frames` and `defcals`: the frames a device's pulse-level jobs may play on, at
  their calibrated frequencies, and its gates' pulses as OpenPulse `defcal`s, which a job may override
- Added a job result's optional `shots`, `meas_level`, `meas_return` and `circuits` (each one's name and number of
  classical bits), which the backend sends with the memory, so the SDK reads a job's result back without its payload

## [2026.11.0-rc.3] - 2026-10-31

### Changed

- Changed a tag's GitHub release notes, which only said "See CHANGELOG.md.", to its CHANGELOG.md section; a tag
  without one now fails the release workflow before it builds anything.

## [2026.11.0-rc.2] - 2026-10-31

### Changed

- Gave every public function and class a Google-style docstring, saying what it does for the caller, its arguments,
  what it returns and what it raises; the OpenAPI schema's descriptions follow them.

### Fixed

- Fixed the GitHub release of a tag getting no installers: it is now published with them, as an immutable release
  took none once published.
- Fixed a release candidate's GitHub release being published as the latest release; it is now a pre-release.

## [2026.11.0-rc.1] - 2026-10-31

### Added

- Added GitLab jobs that, on a `v*` tag, build the deb and macOS installer, upload them to the package registry and
  link them from the GitLab release; the macOS one runs where `PUBLISH_MACOS_ARM64` is `true`, on a runner tagged `macos`.
- Added the dashboard at `/ui`, with `/` redirecting to it, when its build is in the `ui` folder beside `main.py`, as
  the packages ship it.
- Added a deb for amd64, for Debian 13 and Ubuntu 24.04 onwards, and a macOS arm64 installer of Nuitka's standalone
  build, built and attached to the GitHub release of each tag; the deb asks where the database is and provisions it.
- Added `mss start`, the default command, which runs the Alembic or MongoDB migrations and then
  serves, and `mss migrate` and `mss serve`, which do one alone, so a compiled MSS needs no Python checkout.
- Added `--workers` to `mss start` and `mss serve`, defaulting as uvicorn does to `$WEB_CONCURRENCY` or 1. Several
  processes, or MSS instances sharing a database, now start together and send each notice email once.
- Added MongoDB migrations to the start script, as Alembic's for SQL: the pending ones in
  `migrations/mongodb/` apply before MSS starts, so its MongoDB user needs the
  `bypassDocumentValidation` privilege, e.g. the `dbAdmin` role. Each has mongosh scripts too.
- Added the `id`, `user_ids`, `name`, `is_active`, `min_qpu_seconds` and `max_qpu_seconds` filters
  of GET `/admin/projects/` to GET `/me/projects/`, which ignored them, so the dashboard's list of
  active projects also showed inactive ones.
- Added `GET /admin/users/emails/`, a superuser-only lookup of user email addresses behind the
  admin project forms.
- Added an unlogged `GET /health` for the container healthcheck.
- Added `project-membership-granted` and `project-admin-assigned` notifications, emitted when an
  admin creates or edits a project, or approves a request to create one. Being added to a project,
  or handed one to administer, was silent; only removal was announced.
- Added `qpu-seconds-low` and `qpu-seconds-depleted` notifications, raised as a job's usage takes a
  project below `projects.qpu_seconds_low_threshold` (default 600) or to zero. The admin hears about
  running low, admin and members both hear about running out; previously the first sign was a
  rejected job.
- Added an optional email copy of every notification, configured under `[email]` with
  `notices.dashboard_url`. Omit `[email]` and nothing changes. Sending is done by a
  background sweeper reading the notification rows themselves, so an approval is never as slow
  as the mail server and a restart resumes the queue rather than losing it.
- Personal projects are now named after the owner's email local part, e.g.
  `paul.doe (personal)`, so an admin listing projects no longer sees a column of
  identically named rows.
- Added an auto-created personal project for every user, granted on login with
  `projects.personal_qpu_seconds` (default 0). Previously a new user had no project and so
  could not create an app token or submit a job without an admin adding them to one.
- Added DELETE `/me/projects/{_id}/members/{member_id}` so a project admin can remove a member,
  which also revokes that member's app tokens for the project. Previously only a superuser could
  change membership, so a mistaken approval needed an email to an operator.
- Added in-app notifications as notices: GET `/me/notices/`, POST `/me/notices/{id}/dismiss` and
  `/me/notices/{id}/unread` or, for all at once, `/me/notices/dismiss` and `/me/notices/unread`,
  GET/PUT `/me/notices/preferences/` for email opt-outs, and `type` filters on GET
  `/admin/notices` and, with `is_read`, on GET `/counts/notices`. Requesters are now told when a
  request of theirs is decided, and approvers when one needs them; previously neither side
  learned anything without checking the dashboard.
- Added POST `/me/requests/`, GET `/me/requests/` and PUT `/me/requests/{_id}` so users can ask
  to join, create, close or transfer a project, or for QPU time, and whoever may decide can
  approve or reject. Previously only a superuser could change a project.
- Integrated `loguru` for clean, structured, and environment-dependent logging.
- Added flat JSON log formatter in production for seamless Docker and `journalctl` ingestion.
- Added standard logging `InterceptHandler` to capture and route logs from Uvicorn, FastAPI, and Beanie/Motor to Loguru.
- Added smart traceback capture in exception handlers 
  (logs full tracebacks for `500+` server errors, logs `4xx` client errors as warnings without tracebacks).
- Added lifecycle process start/shutdown messages and OAuth2 client provider registration logs.
- Repository: `dev/e2e_native_test.sh` runs the full-stack e2e, with MongoDB, MSS and the backends
  running natively, in about 6 minutes; it needs mongod, mongosh, sqlite3 and uv.
- Dashboard: Added address completion to the "Admin email" and "Member emails" inputs of the admin
  project forms, so a superuser no longer has to recall an address exactly. It is a
  combobox rather than a `<datalist>`, which Firefox and iOS Safari render only partially,
  and it searches the server on a pause in typing rather than filtering one fetched page.
- Dashboard: Added the "Added to project" and "Made project admin" notifications to the bell and to
  the per-type email switches on the settings page.
- Dashboard: Added Approve and Reject buttons to each pending row of the admin requests table, so a
  queue can be cleared without opening every request in turn.
- Dashboard: Added a `/requests` page, under Access in the sidebar, listing the requests the reader has
  made with their status, decision and what was asked for. A requester previously had no way
  to see an outcome except by noticing the notification.
- Dashboard: Added an "Access" group to the sidebar and mobile menu holding Projects and Tokens. Both
  were reachable only from the user menu in the top bar, where a new user never looked.
- Dashboard: Added the low and exhausted QPU-time notifications to the bell and the settings page, so a project
  running out of time is visible before a job is rejected for it.
- Dashboard: Added a `/settings` page, reached from the user menu, with a switch per notification type
  for the email copy. In-app delivery of anything awaiting the reader stays on regardless.
- Dashboard: Added a notifications bell reporting the outcome of project-access and QPU-time requests,
  with approve and reject inline on the ones awaiting the reader. Previously neither
  requester nor approver learned anything without hunting for it.
- Dashboard: Added a "Request project access" dialog on the projects page. It takes a project ID and
  reports an unknown one on the field, so a mistyped ID is self-correcting.
- Dashboard: Added an `/approvals` page where a project admin decides requests for projects they
  administer, reached from a notification or the projects page rather than the nav.
- Dashboard: Added the remaining QPU time of the user's personal project at the foot of the sidebar,
  pointing at the request flow when it is empty.

### Changed

- Changed MSS's SQLite databases to write ahead to a log, synced at checkpoints, so a commit no longer waits on the disk.
- Changed the request log to `bcc_nonces` in MSS's own database, holding only the backends' websocket nonces, one per
  connection, for `bcc_nonce_ttl`, instead of every request in Redis, which MSS no longer needs; `database.redis_url`
  and `request_log_ttl` are ignored.
- MSS needs Python 3.13 or later, and its deb and macOS installer are built with 3.13: built by Nuitka on 3.12, it
  failed about half of many concurrent requests, as CPython 3.12 refuses the compiled functions anyio sorts exception groups with.
- Moved the `api.rest` package into `api`, so the ASGI app is `api:app`.
- `start_mss.sh` runs `main.py start`, after decrypting a SOPS config, instead of migrating and starting uvicorn
  itself, and no longer installs sops or yq; `main.py` serves on the config's `general.mss_port` by default.
- Users sign in through `libs/authlib` instead of fastapi-users and are kept by the storage
  layer instead of Beanie. Emails are now unique in any case, so startup fails while two
  users' emails differ only in case: merge them first.
- Notice severities are numbers in requests, responses and storage (1 critical, 2 warning,
  3 info) and `severity_number` is gone, so posting `"warning"` gets a 422. The start script
  converts stored ones; `python -m migrations.mongodb rollback b109440758fe` undoes it on MongoDB.
- Notices that no longer fit MSS's schema, such as those `v2026.06.0` stored, are left out
  of listings with a warning in the log, where they failed the whole listing; jobs already were.
- `request_log_clean_interval` is ignored, as the request log sweeps its expired entries itself.
- The low and depleted QPU warnings come only from the job that crosses the threshold or zero,
  so the jobs after it do not repeat them.
- A superuser can delete a personal project, for offboarding or an erasure request; only the
  owner is refused, since deleting their own would hand them a fresh allowance on next login.
  An earlier iteration refused everyone, leaving no route but editing the database by hand.
- Project responses now include `is_personal`. Clients asserting on exact response bodies will
  see the new field.
- Removed puhuri support as this is not in the long term plans for maintenance
- [BREAKING]: Changed `/admin/qpu-user-requests` to `/me/requests` endpoints; 
  expanding it to handle all types of user requests
- [BREAKING]: Changed `/admin/bcc-users` to `/admin/bcc/users` endpoints
- [BREAKING]: Changed `/admin/recalibration` to `/admin/bcc/recalibration` endpoints
- [BREAKING]: Changed `/admin/switch` to `/admin/bcc/switch` endpoints
- [BREAKING]: MSS signs a BCC request's `x-mss-is-admin`, method and path as well as its user, nonce and
  timestamp, so they cannot be changed in transit; it needs a BCC that checks the same message, and an older BCC
  refuses its requests with 401.
- [BREAKING]: Changed GET `/me` profile endpoint to GET `/me/profile`
- [BREAKING]: Remove `ext_id`, `source` and `resource_ids` from project schema
- [BREAKING]: Changed the schema of beanie mongodb's strict even at the database level.
- Repository: MSS is the repository: it moved from `apps/tergite-mss` to the root, and the dashboard from
  `apps/tergite-dashboard` into its `ui/`, which builds into the `ui/dist` MSS serves; `apps/` is gone.
- Dashboard: Changed the base path to `/ui/`, where MSS serves the dashboard, in every mode, and the production build to
  call the API on the origin that served it.
- Dashboard: The end-to-end tests run on Playwright instead of Cypress, against MSS and the backends seeded
  from `fixtures/`, as `npm run dev` runs against MSS too; the mock API, Cypress and its plugins are gone.
- Dashboard: The user menu no longer repeats Projects and Tokens, which the sidebar now carries. It
  keeps only what lives nowhere else: Settings and Logout.
- Dashboard: The "Request Pending" button on the projects page now carries how much QPU time was
  asked for. A requester had no way to see the figure they had submitted.
- Dashboard: Notices and the notifications bell now show on the admin screens too; they were
  suppressed under `/admin-*`, so an admin saw a notice only after navigating away. The
  API token control stays off those screens, where no project is selected.
- Dashboard: Submitting an access request now confirms with a toast. The dialog simply closed, which
  was indistinguishable from it having been dismissed.
- Dashboard: [BREAKING]: Projects are known by their ID alone, as MSS dropped `ext_id`: the projects
  tables show and filter by it, the access-request form asks for it, and tokens refer to it.
- Dashboard: The projects page's access-request button is now a primary button reading "Request
  access". As a long outline button it neither stood out nor fitted a phone screen.
- Dashboard: The projects page no longer offers Delete on the reader's own personal project, matching
  the API, which refuses it. The admin projects page still offers it, for offboarding.
- Dashboard: Made sidebar and mobile menu scrollable
- Dashboard: [BREAKING]: Notifications and notices are one thing, as in MSS: the bell lists and counts
  the unread ones from `/me/notices/`, the top banner shows the announcements among them, and
  the settings page has one email switch per notice type at `/me/notices/preferences/`.
- Dashboard: [BREAKING]: Notice severities are numbers, as in MSS, so the admin notices card and the top
  banner sort by `severity`.
- Dashboard: [BREAKING]: Requests of every kind, including the admin requests page and QPU time, go
  through `/me/requests/`; the profile, backend control and email lookup moved to
  `/me/profile`, `/admin/bcc/*` and `/admin/users/emails/` along with MSS.

### Fixed

- Fixed MSS signing its calls to BCC with the client's own `x-request-id`, which let a client choose, or reuse, the
  nonce BCC refuses replays by; each call now has a nonce of MSS's own, and any `x-request-id` is only echoed back.
- Fixed a read of a SQLite database waiting for another connection's write to finish, as every transaction took the
  write lock.
- A device stays online while any of its backend's websockets is open, whichever MSS process holds it; one of them
  closing, as a backend opens one per process, marked the device offline though the others were open.
- A device whose backend, or the MSS process holding its websocket, died without closing it is shown offline within
  90 s, and a switched-off device stays offline when its backend reconnects, until switched on.
- Expired notifications are no longer shown for up to a minute past their `expires_at`, while
  MongoDB's TTL monitor had yet to delete them.
- GET `/jobs/`, `/jobs/{id}` and `/jobs/{id}/status` now show a job only to the user who
  submitted it or an admin; any active project's app token could read any job, decrypted BCC
  token included. Jobs stored without a submitter stay visible to all.
- GET `/counts/job-submitters` now counts the users who submitted jobs between `start_utc` and
  `end_utc`, or every submission with `count_distinct=false`, for admins only; it answered every
  caller with a 500.
- An `x-request-id` header that is not a UUID4 now gets a 400 naming the bad id on the routes
  that read it (job creation, bookings, the admin BCC routes); it was an unexplained 500.
- Fixed GET `/me/profile` reporting `is_superuser` as false for every user, admins included.
- An app token whose user was deleted now gets a 401 on the job routes; it caused a 500.
- An app token of a deactivated user now gets a 401 on the job routes; it kept working.
- The 400 for too many items in a list query param (`id`, `user_ids`, `name`) no longer starts
  its `detail` with `400: `.
- An unhandled server error now answers with a 500 carrying the CORS headers. Errors with no
  handler of their own were turned into a response outside the CORS middleware, so a browser
  reported "Failed to fetch" and a CORS violation instead of the error that actually happened.
- Deciding a request now marks the "please decide this" notification read for every eligible
  approver. Deciding anywhere but the notifications dropdown left the prompt to be cleared by
  hand, once per approver.
- Fixed approving a project access request failing with "Cannot apply $addToSet to non-array
  field" on any project whose member lists were stored as null rather than empty.
- Fixed error OAUTH_USER_ALREADY_EXISTS when a user signs in with a different Oauth provider but same email.
- Dashboard: Logging out now forgets the selected project and API token; they survived the logout, so
  the next user in the same tab started out on the previous user's project.
- Dashboard: Switching project or theme no longer rebuilds the router and remounts every page, which
  threw away open dialogs, form input and scroll position.
- Dashboard: Fixed the device summary's calibration medians, which sorted values as text and counted
  qubits with no value, and the qubit map, which ordered coordinates of 10 and above
  before 2.
- Dashboard: A selected token, project or request now stays selected when its table refetches in a
  different order; selection followed the row position, so the sidebar could switch to
  another item and act on it.
- Dashboard: A row picked while its table refreshes after a delete, create or approval now stays
  picked; the selection was cleared only once the refresh finished, closing its sidebar.
- Dashboard: An error while loading the dashboard or the login page now shows the dashboard's error card
  with working "Try again" and "Back" buttons; the card itself crashed, leaving React Router's
  bare "Unexpected Application Error" page.
- Dashboard: Fixed the days box of the QPU-time request form counting a day as 24 seconds, so 2 days
  asked for 48 seconds on top of the default hour.
- Dashboard: Fixed the QPU-time request form sending a duration other than the one displayed: days,
  hours and seconds showed blank while counting as zero, and emptying a box blocked Submit.

### Removed

- Removed the Docker image and its release jobs; MSS installs from its deb or macOS installer. Job
  upload URLs no longer have `host.docker.internal` replaced with `127.0.0.1`, which only the image needed.
- Repository: The dashboard's Docker image; MSS's deb and macOS installer carry the dashboard's build, which MSS serves at `/ui`.
- Repository: `dev/e2e_test.sh`, which ran the full-stack e2e in docker, and its compose and Dockerfile
  fixtures; `dev/e2e_native_test.sh` runs it, in CI too, in about 6 minutes instead of 10 to 13.
- Repository: `fresh-docker-compose.yml`, `prebuilt-docker-compose.yml` and their `.env.example`; MSS installs
  from its deb or macOS installer and serves the dashboard, as the README's deployment section describes, and `config.alloy` ships MSS's journal instead of docker's logs.
- Repository: The root's own `mss-config.example.toml`; MSS's, which its packages install, is the one example,
  now with the Puhuri note and the `example` OpenID client only the root one had.
- Dashboard: Removed the Docker image, with its nginx config and `run-nginx.sh`; MSS's packages ship the dashboard, which MSS
  serves at `/ui`.

## [2026.06.0] - 2026-06-26

This is part of the tergite release v2026.06.0.

### Added

- Added `/admin/recalibration/{backend}/init`, `/admin/recalibration/{backend}/cancel`
  and `/admin/recalibration/{backend}/info` endpoints for recalibration control
- Added `/admin/switch/{backend}/on` and `/admin/switch/{backend}/off` endpoints to
  turn the backend on and off
- Added POST/GET `/admin/notices`, DELETE `/admin/notices/{notice_id}`,
  POST `/admin/notices/{notice_id}/dismiss` and GET `/counts/notices` for notices
- Dashboard: Added the control panel screen to switch off backends, initialize recalibration and send out notices
- Dashboard: Added the notices banner on top of the dashboard
- Dashboard: Added the `/privacy.html` and `/terms.html` pages
- Dashboard: Added the footer on the dashboard showing the copy right and privacy and terms of use links

### Changed

- Repository: Added notices fixtures to the e2e-test file

## [2026.06.0-rc.2] - 2026-05-28

### Added

- Added `/admin/recalibration/{backend}/init`, `/admin/recalibration/{backend}/cancel`
  and `/admin/recalibration/{backend}/info` endpoints for recalibration control
- Added `/admin/switch/{backend}/on` and `/admin/switch/{backend}/off` endpoints to
  turn the backend on and off
- Added POST/GET `/admin/notices`, DELETE `/admin/notices/{notice_id}`,
  POST `/admin/notices/{notice_id}/dismiss` and GET `/counts/notices` for notices
- Dashboard: Added the control panel screen to switch off backends, initialize recalibration and send out notices
- Dashboard: Added the notices banner on top of the dashboard

### Changed

- Repository: Added notices fixtures to the e2e-test file

## [2026.06.0-rc.1] - 2026-05-13

### Added

- Dashboard: Added the `/privacy.html` and `/terms.html` pages
- Dashboard: Added the footer on the dashboard showing the copy right and privacy and terms of use links

## [2026.03.3] - 2026-03-25

### Added

- Added `is_strict_ip` property to backend config in mss-config.toml
- Repository: Added healthcheck to dashboard service in compose files

### Fixed

-  Fixed connection rejected error when no revers proxy is used

## [2026.03.2] - 2026-03-23

### Fixed

- Repository: Fixed CI error 'pull access denied for tergite/tergite-backend-with-db-e2e, repository does not exist or may require 'docker login'
- Repository: Fixed CI error 'test_insert_default_ttl[payload0] - Failed: DID NOT RAISE &lt;class 'utils.exc.NotFoundError'&gt;'

## [2026.03.1] - 2026-03-20

### Fixed

- Repository: Fixed the "unhealthy" status of the grafana alloy service
- Repository: Fixed failing GitHub actions tests for dashboard

## [2026.03.0] - 2026-03-06

No change

## [2025.12.0] - 2026-03-16

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
- Repository: Added healthchecks for all services in e2e docker compose
- Repository: Added cleanup backend databases via the `/refreshed-db` endpoint in e2e.
- Repository: Added `SERVICE_RESTART` env variable to determine whether the services should restart automatically or not
- Repository: Added `DASHBOARD_EXT_PORT` and `MSS_EXT_PORT` to make the external ports of the mss and dashboard services more configurable
- Dashboard: Added the booking calendar to the device details screen

### Changed

- [BREAKING]: Removed the ability to load mss config toml file in python. One must use the `start_mss.sh` script.
- [BREAKING]: Changed backend connection to MSS to use RSA-secured websockets
- [BREAKING]: Removed the `/devices` and `/calibrations` POST and PUT endpoints
- [BREAKING]: Removed the `/jobs` PUT endpoint
- Repository: Updated e2e tests to include backends that are expected in the dashboard
- Repository: Enforced timezone in cypress tests to Europe/Stockholm
- Repository: Move initialization of e2e's tergite-mongo docker compose service to use a temporary service
- Repository: Removed the `network_mode = none` in the `prebuilt-docker-compose.yml` file
- Repository: Removed the mss-config volume from the dashboard service as it will only be served by environment variables, not mss config file
- Repository: Changed the default version of the images used for mss and the dashboard to `v2025.12.0`
- Repository: Replaced promtail with Grafana alloy for logs collection

### Fixed

- Fixed module 'fastapi_users.schemas' has no attribute 'model_validate'
- Fixed error 'redirect URI '.../auth/{client}/callback' specified in the request does not match the redirect URIs'
- Repository: Fixed e2e error '(0 , crypto**WEBPACK_IMPORTED_MODULE_11**.randomUUID) is not a function'
- Repository: Fixed connection error in production compose settings when connecting to mongodb
- Repository: Fixed 'mongo service already exists' by moving mongo service to the test_mss job and adding the `FF_NETWORK_PER_BUILD: 1` for proper isolation between jobs
- Repository: Fixed 'failed to connect to the docker API at tcp://docker:2375/' in full e2e tests
- Dashboard: Fixed 'dasel: error: unknown flag -r' when run in docker

## [2025.09.0] - 2025-10-02

### Added

- Added filtering bookings by minimum/maximum start timestamps
- Added username property to the Booking data structure

### Changed

- Repository: Add external loki logger support for promtail for linux

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

### Fixed

- Repository: Fix silent errors in e2e tests on Github during cleanup

## [2025.06.1] - 2025-06-16

### Fixed

- Repository: Fix failing e2e tests on Github during cleanup

## [2025.06.0] - 2025-06-16

### Added

- Added more extensive search capability on the GET `/jobs/` endpoints so that one can search by more fields in the job
- Added more extensive search capability on the GET `/devices/` endpoints so that one can search by more fields in the devices
- Added more extensive search capability on the GET `/calibrations/` endpoints so that one can search by more fields in the calibrations
- Added more extensive search capability on the GET `/auth/providers/` endpoints so that one can search by more fields in the auth providers

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
- Repository: BREAKING: Removed v2 from MSS URL in env and docker configs

- Dashboard: Updated API client code to work with new endpoint structure in MSS
- Dashboard: Updated cypress tests to work with new endpoint structure in MSS
- Dashboard: Updated schema for devices in the fixtures

## [2025.03.1] - 2025-03-18

### Changed

- Repository: Changed the backend configurations for the full e2e to run with the new backend configuration files

- Dashboard: Updated the full-e2e fixtures to use the latest backend configuration formats

## [2025.03.0] - 2025-03-14

### Added

- Repository: Added Full end-to-end testing combining the backend, API and dashboard
- Dashboard: Added dark mode color change on dark mode toggle button click
- Dashboard: Added a dark mode toggle button on the login page
- Dashboard: Added a dark mode toggle button on the dashboard page
- Dashboard: Changed the coloring of the device map chart to use muted connection lines
- Dashboard: Changed the coloring of the device bar chart to use purple bar lines, and muted axes

### Changed

- Renamed `quantum_jobs` to `jobs` service
- Removed the api routes, DTOs and service methods for the old WebGUI project.
- Dashboard: Disabled the "live" switch when creating projects as admin

### Fixed

- Dashboard: Fix project list in nav bar to be only active projects

## [2024.12.2] - 2025-01-22

### Changed

- Raise logging level to WARN when app settings are not production
- Remove NETWORK_MODE environment variable

### Fixed

- Fix auth openid errors when auth is disabled

## [2024.12.1] - 2024-12-20

### Added

- Dashboard: Added `run-nginx.sh` script to help initialize/update the variables like cookie names
  API urls and the like in docker prebuilt containers.

### Changed

- Repository: Updated the Github actions to push the ':latest' tag along side the version tag to docker registry
- Repository: Updated `prebuilt-docker-compose.yml` to pick relevant values from the environment as well as
  from `mss-config.toml` for the dashboard docker compose service

### Fixed

- Repository: Fixed the 'parent-folder' image not found error in the Github actions for the dashboard

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
- Repository: Added the admin pages for managing user access in the tergite-dashboard app.
- Repository: Added user access endpoints to the v2 API version of the tergite-mss app.
- Repository: Added the `MSS_PORT` environment variable to the `.env.example` to configure the port on which tergite-mss runs on in docker compose.
- Repository: Added the `NETWORK_MODE` environment variable to the `.env.example` to configure the `network_mode` to use in docker compose file
- Dashboard: Added the tokens list page for viewing, editing and deleting tokens of current user
- Dashboard: Added the projects list page for viewing, requesting QPU time and deleting projects for current user
- Dashboard: Added admin page for viewing, and approving user requests
- Dashboard: Added admin page for viewing, editing, deleting and creating new projects
- Dashboard: Added close button on the job detail drawer on the home page

### Changed

- Dashboard: Changed devices page to show 'no devices found' when no devices are available.
- Dashboard: Changed to show sidebar placeholder on admin user requests page when no user request is selected

### Fixed

- Fixed the not found error when deleting expired app tokens
- Fixed httpx version to 0.27.2 as 0.28.0 removes many deprecations that we were still dependent on in FastAPI testClient

## [2024.09.1] - 2024-09-24

### Added

- Added example scopes in the mss_config.example.toml
- Added units 'Hz' and 's' to calibration data schema
- Dashboard: Added units 'Hz' and 's' to calibration data schema
- Dashboard: Changed all properites of calibration data to be optional
- Dashboard: Added normalizing calibration data to have frequencies in GHz and durations in microseconds

### Changed

- Removed `archives` folder
- Removed `dev` folder
- Changed all calibration v2 properties optional

### Fixed

- Fixed CORS error when dashboard and MSS are on different domains or subdomains
- Fixed 'AttributeError: 'NoneType' object has no attribute 'resource_usage'' on GET /v2/me/jobs

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
- Repository: Added the tergite-dashboard app
- Dashboard: Initial version
- Dashboard: Device summary list on the dashboard home
- Dashboard: Jobs list on the dashboard home
- Dashboard: Jobs detail drawer on the dashboard home
- Dashboard: Device list page
- Dashboard: Device detail page
- Dashboard: Error page

### Changed

- Repository: Removed the tergite-landing-page app
- Repository: Removed the tergite-webgui app

## [2024.04.1] - 2024-05-28

### Added

- Added ability to handle multiple Tergite backends

### Changed

- Updated the contributions guidelines and the government model
- Repository: Updated the contribution guidelines and government model statements

## [2024.04.0] - 2024-04-16

### Added

- Repository: Added the tergite-landing-page constituent app
- Repository: Added the tergite-mss constituent app
- Repository: Added the tergite-webgui constituent app
- Repository: Added github actions for all constituent apps
- Repository: Added the docker compose [`./prebuilt-docker-compose.yml`](./prebuilt-docker-compose.yml) for pre-built image
- Repository: Added the docker compose file [`./fresh-docker-compose.yml`](./fresh-docker-compose.yml) for cases when the constituent apps have to be built on the fly.

### Changed

- Moved tergite-mss to the tergite-frontend monorepo
- Changed configuration control to use `mss-config.toml` not `.env`
- Removed the `auth_config.toml` file
- Repository: Updated the README.md

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

## [2023.12.0] - 2024-03-06

This is part of the tergite release v2023.12.0 that is the last to support [Labber](https://www.keysight.com/us/en/products/software/application-sw/labber-software.html).
Labber is being deprecated.

### Added

- Initial release of the tergite-mss server
- Added support for the [WebGUI](https://github.com/tergite/tergite-webgui)
