# Tergite MSS — System Design

The Main Service Server: the public REST API of the Tergite stack. It owns all persistence,
all authentication and authorization, and it is the only component allowed to talk to the
quantum backends (BCC instances).

Read [../../DESIGN.md](../../DESIGN.md) first for the monorepo context, deployment and the
cross-app conventions. Existing narrower docs — [docs/api-design.md](./docs/api-design.md),
[docs/auth.md](./docs/auth.md), [docs/backends.md](./docs/backends.md) — remain the
reference for REST conventions, the OAuth2 setup recipe and adding a backend; this document
is the map that ties them together.

## 1. Architecture: service-oriented

MSS is organised by **service**, not by technical layer. Each service under `services/` is a
self-contained slice of the domain: its DTOs, its persistence, its business rules, and —
where it needs them — its own routers. `api/` is a thin HTTP adapter on top: it wires
routers together, injects dependencies, and translates domain exceptions to status codes.
It should hold no business logic.

```
apps/tergite-mss/
├── settings.py              # loads + validates config at import time; fails fast
├── start_mss.sh             # from a checkout: decrypt a SOPS config → main.py start
├── api/                     # HTTP adapter layer
│   └── rest/
│       ├── __init__.py      # the FastAPI app: middleware, exception handlers, routers
│       ├── app_kwargs.py    # app metadata + lifespan (startup/shutdown)
│       ├── auth.py          # the auth backends, and the current user and project dependencies
│       ├── database.py      # opens the one Database in the lifespan; get_database
│       ├── dependencies.py  # every injectable, as an Annotated alias
│       ├── errors.py        # the exception handlers
│       ├── middleware.py    # RequestIDMiddleware
│       ├── users.py         # the user manager, which gives each user a personal project
│       ├── utils.py         # router-level helpers (request id, BCC ws verification)
│       └── routers/         # one module per URL prefix
│           ├── admin/           /admin (projects in admin/projects.py)
│           ├── auth.py          /auth
│           ├── booking.py       /bookings
│           ├── calibrations.py  /calibrations
│           ├── counts.py        /counts
│           ├── jobs.py          /jobs
│           ├── me/              /me (projects.py, tokens.py)
│           └── devices/         /devices  (+ the websocket; its event handlers are in services/devices)
├── services/                # the domain
│   ├── auth/                # users, projects, app tokens, providers, user requests
│   ├── calibration/
│   ├── devices/
│   ├── jobs/
│   ├── notices/
│   └── external/bcc/        # outbound client to the quantum backends
├── libs/storage/            # Database, Schema and the stores behind them; imports no app code
├── libs/authlib/            # users and sessions, from fastapi-users 14.0.2 (MIT); imports no app code
├── utils/                   # cross-cutting, domain-agnostic helpers
├── dev/openapi/             # export.py and the openapi.json it writes: the API contract
└── tests/
```

### The shape of a service

A service is a package. Its public surface is what `__init__.py` exposes; callers import
`from services import jobs as jobs_service` and use module-level functions.

| File | Contains |
| --- | --- |
| `dtos.py` | Pydantic models — request bodies, responses, and the `libs.storage` `Schema`s that are also the persistence schema. Query-param models too. |
| `service.py` | The business logic: module-level `async def` functions taking the `Database` as their first argument. |
| `exc.py` | Service-specific exceptions. |
| `on_startup(...)` | Config from the app lifespan. |

A service's `__init__.py` is its facade: it only re-exports, with `__all__` as strings. Code
outside the service imports from the facade (`from services.jobs import Job`), never from its
`dtos.py` or `service.py`; `tests/test_styleguide.py` checks this. Each `services/external/`
package is a service of its own.

### Why the layering matters

A router should read as: resolve dependencies → call one or two service functions → wrap the
result in a response envelope. Persistence details, BCC protocol details and cross-entity
rules live in `services/`. Two consequences worth internalising:

- Services take the `Database` as a parameter; they never reach for a global connection.
  This is what makes them testable and what lets the lifespan own the connection.
- `services/` may import `utils/` and other services (e.g. `devices` events call `jobs` and
  `calibration`). `services/` must not import from `api/`.
- Only `api` reads `settings`. A class gets its config in its constructor (`BccClient`,
  `Emailer`). A module whose functions are called from many places, or from `default_factory`
  fields, gets it once from the lifespan through its `on_startup` (`notices`, `jobs`, `auth`)
  or a setter (`date_time.set_datetime_precision`) and keeps it module-private.

## 2. Runtime

### Startup

`main.py start`, the default command, migrates the database and then serves `api:app`
with uvicorn on the config's `general.mss_port`; `migrate` and `serve` do one alone. The
packages run it as `tergite-mss start`. From a checkout, `start_mss.sh` does the same, after
SOPS-decrypting `MSS_CONFIG_FILE` (default `mss-config.toml`) into `MSS_CONFIG_JSON_STR` with
`sops` and `yq` when it carries a `hc_vault` block.

`settings.py` then validates that JSON into `AppConfig` and asserts the private key file
exists. Any config error is a startup crash, not a runtime surprise.

The FastAPI `lifespan` in `app_kwargs.py` creates the BCC httpx clients, opens the
`Database` (whose `setup` creates every schema's collection, validator and indexes) and the
request log's, then runs the `on_startup` of `auth` (which stores the roles users may hold),
`jobs` and `notices`, and, when `[email]` is configured, starts the only background loop in the
app: the `Emailer` sending the notices' pending emails. On shutdown it stops the emailer, closes the BCC clients, closes all
device websockets, marks every device disconnected, and closes both databases.

`docs_url` / `redoc_url` / `openapi_url` are set to `None` unless
`general.environment == "development"` — there are no interactive docs in production.

### Per-request pipeline

1. **`CORSMiddleware`** — Starlette's, with `allow_origin_regex=".*"`, so that it mirrors the
   request `Origin` back instead of `*`, because the auth cookie requires credentialed CORS.
2. **`request_logging_middleware`** — resolves or generates a request ID (reusing an
   incoming `x-request-id`), binds it into the loguru context so every log line in the
   request carries it, logs start/finish with duration, records the request id with
   `request_log.record_request`, and echoes `x-request-id` back on the response.
3. **Dependencies** — everything injectable is a named `Annotated` alias in
   `api/dependencies.py` (`DatabaseDep`, `CurrentUserDep`, `BccClientDep`,
   `RequestIdDep`, …), one name per dependency, each ending in `Dep`. Routers take them as
   parameters (`user: CurrentUserDep`), never the raw `Depends(...)` expression, and a route
   that only needs the check still names the parameter (`requester: CurrentSuperuserDep`).
   Add new injectables there.
4. **Exception handlers** — domain exceptions from `utils/exc.py` are mapped to status codes
   centrally in `api/__init__.py`, with the handlers `api/errors.py` makes:
   `InvalidInputError` (and its `TooManyListQueryParams`) / `UnknownBccError` /
   `InvalidRequestIDError` → 400, `UnauthorizedError` → 401,
   `ForbiddenError` → 403, `NotFoundError` → 404, `ConflictError` → 409,
   `ServiceUnavailableError` → 503, `BccHttpError` → the BCC's
   own status, and `ValueError` / `TypeError` / `RuntimeError` / bare `Exception` → 500
   with a generic message, and
   `UnsupportedOauthException` → 500 with its own. Other service exceptions subclass these
   and need no mapping of their own. **Raise domain exceptions from services; do not raise
   `HTTPException` there.**

## 3. Authentication and authorization

Users sign in through `libs/authlib`, which began as a copy of
[fastapi-users](https://fastapi-users.github.io/); projects and app tokens are
`services/auth/`'s own. Two orthogonal mechanisms; most endpoints need one specific one.

### Users — who you are

- Login is **OAuth2/OpenID only**; there is no password login and authentication cannot be
  disabled (the old `auth.is_enabled` flag is gone).
- Each `[[auth.clients]]` entry is an `authlib.OAuthProvider`, served by one router at
  `/auth/{provider}/…` (plus a legacy `/auth/app/{provider}/…` alias); an unknown provider
  is a 404. Routes: `authorize`, `auto-authorize` (redirects immediately — this is what the
  dashboard links to), `callback`.
- `email_regex` gates which emails may use a given provider; `roles` are granted on sign-in;
  `email_domain` is what `GET /auth/providers/?email_domain=…` matches so the login page can
  offer the right button; `associate_by_email` decides whether a returning user who used a
  different provider is linked to the existing account.
- One session JWT, read from the **bearer header**, then the **cookie** the callback sets
  (the dashboard's). Roles are `user`, `researcher`, `admin`, `partner`, `system`;
  `is_superuser` is derived from having `admin`.
- Dependencies: `GET_CURRENT_USER`, `GET_CURRENT_USER_ID`, `GET_CURRENT_SUPERUSER`, from the
  `authlib.Auth` that `api/auth.py` builds from the auth config; routers use them
  through `api/dependencies.py`. authlib's errors are answered by the handler
  `add_exception_handlers` registers in `api/__init__.py`.

### Projects and app tokens — what you may spend

- An **app token** is a database-backed bearer token scoped to *(user, project)* with a
  lifespan. Created in the dashboard; revocable; this is what the SDK and other Tergite
  components use.
- A **project** carries `qpu_seconds`. Creating a job requires an active project with
  positive `qpu_seconds`. Job completion decrements it via `update_qpu_usage`.
- Dependencies, also in `api/auth.py`: `get_current_project_user_ids` (strict, enforces
  QPU seconds) and `get_current_lax_owner` (lax, for reads). Each checks the token's project
  and user against an `AccessRule` from `services/auth/access.py`: a missing token or an
  inactive project is 401, too few QPU seconds or a missing role is 403.
- A JWT is **not** interchangeable with an app token: a JWT works on `/auth…`, `/me…` and
  admin routes; an app token works on the resource routes. Using the wrong one yields
  401/403, which is the single most common confusion when testing by hand.

The interaction diagram for the full flow (via MyAccessID) is in
[docs/auth.md](./docs/auth.md) with the editable drawio source in `docs/assets/`.

## 4. Talking to the backends

`services/external/bcc/service.py` holds a process-global map of `BccClient`s, one per
`[[backends]]` entry, created in the lifespan with the MSS private key it loads once.
`bcc.get_client(backend)` looks one up and
raises `UnknownBccError` for an unknown name; `BccClientDep` calls it with the `{backend}`
path param, and the jobs router calls it with the job's device.

Every outbound call goes through `BccClient._request`, which signs the request
(`x-mss-request-id`, `x-mss-timestamp`, `x-mss-signature`, `x-mss-user-id`, optional
`x-mss-is-admin`), raises `BccHttpError` with the status of a BCC error response, and
turns connection/timeout failures into `ServiceUnavailableError` → 503. Client methods:
`get_token`, `cancel_job`, `delete_job`, `view_users`, `create_user`, `delete_user`,
`create_booking`, `cancel_booking`, `view_bookings`, `view_bookings_configs`,
`init_recalibration`, `get_recalibration_info`, `stop_recalibration`, `switch_off`,
`switch_on`.

`services/external/email/` is the other outbound client: an `Emailer` that sends, every
`email_sweep_interval` seconds, the batch of pending notice emails that
`services/notices/emails.py` yields, and records each result through its callback. Nothing on
a request path sends mail, so a dead mail server cannot fail a request.

**Bookings and BCC users are not persisted by MSS.** The `/bookings` and
`/admin/bcc-users` routes proxy to the owning backend on the user's behalf. Only jobs,
devices, calibrations, notices and the auth entities live in MongoDB.

### Inbound: the device websocket

`WS /devices/ws/{name}` is how a backend pushes state. The handshake is verified by
`get_verified_device_name` (signature, source IP, nonce freshness, nonce replay) and the
socket is registered with the router's `WebsocketConnectionManager` (`connections.py` beside it). Each JSON frame is a
`DeviceEvent` dispatched through `EVENT_HANDLERS` in `services/devices/events.py` to the
handler for its name:

| Event | Handler effect |
| --- | --- |
| `initialized` | upsert the device document |
| `recalibrated` | insert calibration into `calibrations` + append to `calibrations_logs` |
| `job_updated` | update the job; on first resource-usage report, decrement project QPU seconds |
| `switched_off` | `is_online = false`, stamp `last_online` |
| `switched_on` | `is_online = true`, clear `last_online` |

Handlers reply with an `EventResponse` per frame and never kill the socket: validation
errors become `{"status": "error", "detail": …}`, and a device attempting to edit another
device's record raises `ForbiddenError` → `forbidden`. Adding an event means adding an
enum member in `services/devices/dtos.py`, and a handler and its entry in `EVENT_HANDLERS` in
`services/devices/events.py`.

## 5. Data

MSS reaches its data through `libs/storage`: one `Database`, opened in the lifespan with
every service's `SCHEMAS` and handed to routes as `DatabaseDep`, beside the request log's
own on Redis (below). The `Database` picks its store from the URL's scheme: `MongoStore`
for `mongodb://`, `SqlStore` for a SQLAlchemy URL with an async driver
(`postgresql+asyncpg://`, `sqlite+aiosqlite://`), `RedisStore` for `redis://`. Nothing
outside `libs/storage/<store>` names a database technology.

A schema is a Pydantic `Schema` whose `__storage__` names its table, key, unique fields,
indexes, expiring field, references and `indexed_lists`. Services query it in MongoDB's own
dialect, kept to what every store can translate: `filter={"user_id": {"$in": [user_id,
None]}}`, `update={"$set": {…}, "$inc": {…}}`, `sort=["-created_at"]`, `skip`, `limit`.
`Database` refuses an unknown operator or field, and an update that would change a key,
before a store sees it, and a service builds its filters privately from its arguments;
routes never build one. Ids are `Id` strings, which MongoDB keeps as ObjectIds. No store
reads a record past its expiring field. A schema with `should_skip_invalid` has `get` and
`find` leave out stored records that fail validation, with a warning naming the invalid
fields, where any other read raises; writes always raise, and `count` includes them.
Jobs and notices set it, as MongoDB holds older shapes of both.

- **MongoDB** keeps a collection per schema, with a `$jsonSchema` validator and the indexes
  `__storage__` asks for; a TTL index deletes expired records. A revision that changes stored
  values has a JSON of updates, both ways, named after it in `migrations/mongodb/`. The start
  script applies the pending ones in Alembic's order (`python -m migrations.mongodb upgrade`),
  bypassing the old MSS's validator, as `setup` replaces it only once MSS starts; its
  `.upgrade.js` and `.rollback.js` apply the same JSON with mongosh, and both record it in
  `mongodb_migrations`.
- **SQL** gets a table per schema from `libs/storage/sql/tables.py`: a column per scalar
  field, a `JSON` column per nested one (read and written whole, never queried), a `row_id`
  that keeps insertion order, and a child table, one row per element, for each list in
  `indexed_lists` or `references` (`auth_project_user_ids`, `notice_dismissed_by`,
  `request_target_user_ids`). A list of models gets a column per element field; it is set
  whole and matched by element with `$elemMatch`, as a user's OAuth accounts are. A query on a JSON field, or a write to part of one, is refused,
  and is the signal to give it a table of its own. Alembic migrates the tables
  (`migrations/`), and `tests/test_migrations.py` fails when a schema changed without a
  revision. A task deletes expired rows hourly, as SQL has no TTL index.
- **`tests/libs/storage/test_conformance.py`** runs every `Database` method on MongoDB,
  PostgreSQL and SQLite, and each service's storage test (`tests/services/*/test_*_storage.py`)
  runs on all three too.

Users are records like any other: `auth_users`, keeping the documents fastapi-users wrote
field for field, with roles referencing `auth_roles` and OAuth accounts in a list of models.

Notable tables: `jobs`, `devices`, `calibrations`, `calibrations_logs` (historical,
indexed on `(name, last_calibrated desc)`), `notices` (expiring at `expires_at`).
Deleting a project moves it to `deleted_auth_projects` rather than dropping it.

**Request logs** (`services/request_log`) remember each request id and websocket nonce for
`request_log_ttl` seconds. They are written on every request, so they live in a cache: a
`Database` of their own on `database.redis_url`, whose `RedisStore` keeps them in the
`request_logs` hash keyed by `request_id`, each expiring with its `expires_at`.
`record_request` returns False for an id already recorded: that is how a replayed nonce is
refused, in one write.

## 6. REST conventions

Codified in [docs/api-design.md](./docs/api-design.md); the short version:

- URLs are `/{resource}/({id})`. Every resource has a DTO named after it.
- List endpoints return `{"skip": int, "limit": int | null, "data": [...]}` — build it with
  `get_paginated_json(data, skip, limit)`, and declare `PaginatedListResponse[Item]` as the
  route's response.
- Action endpoints return `{"status": ..., "message": ...}` (`GeneralMessage`).
- Errors return `{"detail": "..."}` with a non-2xx status — produced by the central handlers,
  not per-route try/except.
- List filtering is a Pydantic query model injected with `Depends()` (e.g. `JobQuery`,
  `DeviceQuery`), usually built by `create_partial_model` so every field is optional.
  `sort` is a repeated query param where a leading `-` means descending.
- Property-only sub-resources (e.g. `GET /jobs/{id}/status`) are allowed only when that
  property is requested far more often than the whole object, and return `{"{property}": …}`.
- Every route declares its response, so the OpenAPI schema describes every body. A route that
  returns a model gets it as a return annotation. A route that returns a prebuilt dict, or a
  model whose own `model_dump` shapes the body (`Job`, `Project`, `Device`, the paginated
  list), declares `responses={200: {"model": …}}` instead: a `response_model` would
  re-serialise the body and undo that shaping.
- `dev/openapi/openapi.json` is the committed schema, written by `python -m dev.openapi.export`
  with the test config. `tests/test_openapi.py` fails when it no longer matches the app.

### Endpoint map

| Prefix | Auth | Notes |
| --- | --- | --- |
| `/auth/{provider}/…` | — | `authorize`, `auto-authorize`, `callback`; plus `GET /auth/providers/` and `POST /auth/logout`. There is no password-login route — `get_auth_router` only registers logout. |
| `/me` | JWT | current user; `/me/jobs/`, `/me/projects/…`, `/me/tokens/…` |
| `/devices` | app token / open reads | `GET /`, `GET /{name}`, `WS /ws/{name}` |
| `/calibrations` | open reads | `GET /`, `GET /{name}`; public device data, like `/devices` |
| `/jobs` | app token (strict on POST) | list, get, `/{id}/status`, create, `/{id}/cancel`, delete; reads return only the token user's jobs (and jobs with no recorded submitter) unless the user is an admin |
| `/bookings/{backend}` | JWT | proxied to BCC; create, cancel, list, `/config` |
| `/counts` | JWT | `/notices`; `/job-submitters` (superusers only) |
| `/admin` | superuser / specific roles | `/projects/…`, `/qpu-time-requests/`, `/user-requests/{id}`, `/bcc-users/{backend}/…`, `/recalibration/{backend}/…`, `/switch/{backend}/on|off`, `/notices/…` |

## 7. Testing

`pytest` with a real MongoDB, PostgreSQL, SQLite and Redis — no database mocking. `tests/conftest.py`
calls `setup_test_env()` **before any app import**, because `settings.py` reads config at
import time; keep that ordering when adding fixtures.

- `tests/_utils/` — shared helpers, grouped by what they do: `auth.py`, `bcc.py`,
  `storage.py`, `fixtures.py`, `records.py`, `env.py`, `json.py`, `date_time.py`,
  `mock_backend.py`, `modules.py`, `numbers.py`, `types.py`. Put new helpers here, in the
  file that matches their job — not in a single `utils.py` and not in scattered
  `fixtures/*.py` modules.
- `tests/fixtures/` — JSON data and the RSA key pairs used to exercise the MSS↔BCC
  signature paths.
- `tests/api/test_*.py` — one file per router, driven through `TestClient`.
- `mock_backend.py` stands in for BCC; `respx` intercepts httpx calls.
- The app starts once per session, as its startup is the slow part: the `client` fixture's
  `with` block neither starts nor stops it, and clears its cookies afterwards. A fixture that
  changes what the app starts with (`unconfigured_email`) is listed in
  `_FRESH_APP_FIXTURES`, and its test gets a client that starts the app afresh.
- What each database does differently is the storage layer's to get right, so the
  conformance and storage tests run on MongoDB, PostgreSQL and SQLite. The API tests run
  once, on the database `TEST_DATABASE_URL` names (the test config's MongoDB if unset): the
  session-scoped `api_database` fixture empties it and points the app at it. The `db`
  fixture is that database, as a `SyncDatabase` from `tests/_utils/storage.py` that a
  synchronous test seeds and reads through, records not documents; it empties every table
  afterwards but the roles and notice templates the app writes at startup. Tests must not
  assume a clean store beyond what it gives them.

CI runs `black --check .`, `pyflakes`, then `pytest` on Python 3.12 and 3.13.

## 8. Python style

On top of the shared rules in [../../DESIGN.md](../../DESIGN.md#style-guide):

- **`black` is authoritative** for formatting (pinned `black==23.11.0`, a CI gate); `isort` for imports, configured with `profile = "black"` so the two agree —
  without it isort emits a style black then reformats, churning unrelated files. Run both
  before committing; neither needs flags.
- **`pyflakes`** finds unused imports and variables; CI runs it over `api services utils
  libs migrations settings.py tests dev` and fails on any finding.
- **Constants go at the top of the file**, after imports — not buried between functions. The
  exception is a constant built from a function or class defined in the same file, which
  stays after it (e.g. `EVENT_HANDLERS` after the handlers, `ProjectPartial`
  after `Project`).
- **Module-private helpers** (`_name`, not used outside the module) go at the **bottom**,
  unless definition order forces otherwise. `_extract_error_message` and `_create_headers`
  at the end of `bcc/service.py` are the pattern.
- **No banner comments** at any indent. Give the group a real docstring, split it into its
  own file, or delete the banner when the docstring below already says it.
- **Docstrings**: one line where one line does. Where a function takes several arguments or
  raises domain exceptions the codebase uses the Google style already present —
  `Args:` / `Returns:` / `Raises:`, listing the exception messages callers can expect. That
  is the useful case; a short obvious helper needs nothing.
- **Names say what a thing is.** Variables are nouns naming their content (`notice_filter`,
  never `where`). No `build_*` functions: a constructed thing is a class's constructor,
  anything else a `get_*`; `tests/test_styleguide.py` rejects `build` as a verb.
- **Obvious beats clever.** An `if`/`else` returning each whole literal, one explicit `if`
  per optional field; not loops over tuples of fields, comprehensions that build operators,
  merged dicts, or one helper returning two things to pull apart.
- **A value that is only defined stays at its use.** No function that just returns a
  literal (a dict, a filter, an update); write it where it is used. Functions are for real
  actions: I/O, a check that raises, a computation with steps.
- **Type hints everywhere**, including `async def` return types. DTOs are Pydantic models,
  never bare dicts crossing a service boundary.
- **License header** on every new file: copy the block from a neighbouring module and add
  the copyright line for the contributing party.

## 9. Adding things — where to start

| Task | Path |
| --- | --- |
| New endpoint on an existing resource | the router in `api/routers/`, plus a service function; add a `tests/api/test_*.py` case |
| New resource | new package under `services/` (`dtos.py` + `service.py`, `on_startup` if it needs indexes), new router module, include it in `api/__init__.py` |
| New injectable | an `Annotated` alias in `api/dependencies.py` |
| New OAuth2 provider | a `[[auth.clients]]` block — no code; see [docs/auth.md](./docs/auth.md) |
| New quantum backend | a `[[backends]]` block plus its public key — no code; see [docs/backends.md](./docs/backends.md) |
| New device event | enum member in `services/devices/dtos.py`, handler and `EVENT_HANDLERS` entry in `services/devices/events.py` |
| New config option | a field on the right model in `utils/config.py` **and** a documented entry in `mss-config.example.toml` |
| New BCC call | a method on `BccClient` using `self._request`, so signing and error mapping are inherited |
