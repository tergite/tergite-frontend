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
where it needs them — its own routers. `api/rest/` is a thin HTTP adapter on top: it wires
routers together, injects dependencies, and translates domain exceptions to status codes.
It should hold no business logic.

```
apps/tergite-mss/
├── settings.py              # loads + validates config at import time; fails fast
├── start_mss.sh             # entrypoint: parse/decrypt config → uvicorn
├── api/                     # HTTP adapter layer
│   └── rest/
│       ├── __init__.py      # the FastAPI app: middleware, exception handlers, routers
│       ├── app_kwargs.py    # app metadata + lifespan (startup/shutdown)
│       ├── dependencies.py  # every injectable, as an Annotated alias
│       ├── middleware.py    # TergiteCORSMiddleware
│       ├── utils.py         # router-level helpers (request id, BCC ws verification)
│       └── routers/         # one module per URL prefix
│           ├── admin.py         /admin
│           ├── auth.py          /auth
│           ├── booking.py       /bookings
│           ├── calibrations.py  /calibrations
│           ├── counts.py        /counts
│           ├── jobs.py          /jobs
│           ├── me.py            /me
│           └── devices/         /devices  (+ the websocket and its event handlers)
├── services/                # the domain
│   ├── auth/                # users, projects, app tokens, providers, user requests
│   ├── calibration/
│   ├── devices/
│   ├── jobs/
│   ├── notices/
│   └── external/bcc/        # outbound client to the quantum backends
├── utils/                   # cross-cutting, domain-agnostic helpers
└── tests/
```

### The shape of a service

A service is a package. Its public surface is what `__init__.py` exposes; callers import
`from services import jobs as jobs_service` and use module-level functions.

| File | Contains |
| --- | --- |
| `dtos.py` | Pydantic models — request bodies, responses, and Beanie `Document`s (which double as the persistence schema). Query-param models too. |
| `service.py` *(or the functions in `__init__.py`)* | The business logic: module-level `async def` functions taking the db handle as their first argument. |
| `database.py` | Only where a service needs a repository object rather than free functions (the `auth` submodules). |
| `routers.py` | Only where the service owns routes that are mounted by an `api/rest/routers/*` module — used by `auth` for the fastapi-users-derived routers. |
| `manager.py`, `authenticator.py`, `strategy.py`, `auth_backend.py` | fastapi-users extension points; `auth` only. |
| `exc.py` | Service-specific exceptions. |
| `on_startup(db)` | Index creation / Beanie init, called from the app lifespan. |

Some services put their logic directly in `__init__.py` (`jobs`, `calibration`,
`user_requests`), others in a `service.py` re-exported by `__init__.py` (`devices`,
`notices`, `auth`, `external.bcc`). Both are current; prefer `service.py` for anything
non-trivial and keep `__init__.py` as the facade.

### Why the layering matters

A router should read as: resolve dependencies → call one or two service functions → wrap the
result in a response envelope. Persistence details, BCC protocol details and cross-entity
rules live in `services/`. Two consequences worth internalising:

- Services take `db: AsyncIOMotorDatabase` as a parameter; they never reach for a global
  connection. This is what makes them testable and what lets the request-scoped dependency
  own connection lifetime.
- `services/` may import `utils/` and other services (e.g. `devices` events call `jobs` and
  `calibration`). `services/` must not import from `api/`.

## 2. Runtime

### Startup

`start_mss.sh` → reads `MSS_CONFIG_FILE` (default `mss-config.toml`), SOPS-decrypts it if it
carries a `hc_vault` block, converts TOML → JSON with `yq`, exports it as
`MSS_CONFIG_JSON_STR`, and starts `uvicorn api.rest:app` (with `--reload` outside
production, and `--forwarded-allow-ips` when it detects `/.dockerenv`).

`settings.py` then validates that JSON into `AppConfig` and asserts the private key file
exists. Any config error is a startup crash, not a runtime surprise.

The FastAPI `lifespan` in `app_kwargs.py` creates the BCC httpx clients, then runs each
service's `on_startup(db)`: Beanie document registration for `auth`, `notices`, `notifications`
and `qpu_grants`, index creation for `calibration` and `notices`. It then starts the only
background loop in the app, `notifications.start_sweeper()`, which is a no-op unless `[email]`
is configured. On shutdown it stops the sweeper, closes the BCC clients, closes all device
websockets, and marks every device disconnected.

`docs_url` / `redoc_url` / `openapi_url` are set to `None` unless
`general.environment == "development"` — there are no interactive docs in production.

### Per-request pipeline

1. **`TergiteCORSMiddleware`** — a `CORSMiddleware` subclass that always mirrors the request
   `Origin` back instead of `*`, because the auth cookie requires credentialed CORS.
2. **`request_logging_middleware`** — resolves or generates a request ID (reusing an
   incoming `x-request-id`), binds it into the loguru context so every log line in the
   request carries it, logs start/finish with duration, records the request in the Redis
   request-log store, and echoes `x-request-id` back on the response.
3. **Dependencies** — everything injectable is a named `Annotated` alias in
   `api/rest/dependencies.py` (`MongoDbDep`, `CurrentProjectDep`, `BccClientDep`,
   `RequestIdDep`, …). Routers depend on those aliases, never on the raw `Depends(...)`
   expression. Add new injectables there.
4. **Exception handlers** — domain exceptions from `utils/exc.py` are mapped to status codes
   centrally in `api/rest/__init__.py`: `InvalidInputError` (and its `TooManyListQueryParams`)
   / `UnknownBccError` / `InvalidRequestIDError` → 400, `UnauthorizedError` → 401,
   `ForbiddenError` → 403, `NotFoundError` → 404, `ConflictError` → 409,
   `TooManyRequestsError` → 429, `ServiceUnavailableError` → 503, `BccHttpError` → the BCC's
   own status, and `ValueError` / `TypeError` / `RuntimeError` / `DbValidationError` /
   `DatabaseError` / bare `Exception` → 500 with a generic message, and
   `UnsupportedOauthException` → 500 with its own. Other service exceptions subclass these
   and need no mapping of their own. **Raise domain exceptions from services; do not raise
   `HTTPException` there.**

## 3. Authentication and authorization

Built on [fastapi-users](https://fastapi-users.github.io/) with Beanie, extended in
`services/auth/`. Two orthogonal mechanisms; most endpoints need one specific one.

### Users — who you are

- Login is **OAuth2/OpenID only**; there is no password login and authentication cannot be
  disabled (the old `auth.is_enabled` flag is gone).
- One client per `[[auth.clients]]` entry is registered at startup at `/auth/{name}/…`
  (plus a legacy `/auth/app/{name}/…` alias). Routes: `authorize`, `auto-authorize`
  (redirects immediately — this is what the dashboard links to), `callback`.
- `email_regex` gates which emails may use a given provider; `roles` are granted on sign-in;
  `email_domain` is what `GET /auth/providers/?email_domain=…` matches so the login page can
  offer the right button; `associate_by_email` decides whether a returning user who used a
  different provider is linked to the existing account.
- Two backends over the same JWT strategy: **cookie** (`JWT_COOKIE_BACKEND`, the dashboard)
  and **bearer header** (`JWT_HEADER_BACKEND`). Roles are `user`, `researcher`, `admin`,
  `partner`, `system`; `is_superuser` is derived from having `admin`.
- Dependencies: `GET_CURRENT_USER`, `GET_CURRENT_USER_ID`, `GET_CURRENT_SUPERUSER`.

### Projects and app tokens — what you may spend

- An **app token** is a database-backed bearer token scoped to *(user, project)* with a
  lifespan. Created in the dashboard; revocable; this is what the SDK and other Tergite
  components use.
- A **project** carries `qpu_seconds`. Creating a job requires an active project with
  positive `qpu_seconds`. Job completion decrements it via `update_qpu_usage`.
- Dependencies: `GET_CURRENT_PROJECT` (strict — enforces QPU seconds),
  `GET_CURRENT_LAX_PROJECT` (`ignore_qpu_seconds=True`, for reads),
  `GET_CURRENT_SYSTEM_USER_PROJECT` (requires the `system` role),
  `GET_CURRENT_PROJECT_USER_IDS`.
- A JWT is **not** interchangeable with an app token: a JWT works on `/auth…`, `/me…` and
  admin routes; an app token works on the resource routes. Using the wrong one yields
  401/403, which is the single most common confusion when testing by hand.

The interaction diagram for the full flow (via MyAccessID) is in
[docs/auth.md](./docs/auth.md) with the editable drawio source in `docs/assets/`.

## 4. Talking to the backends

`services/external/bcc/service.py` holds a process-global map of `BccClient`s, one per
`[[backends]]` entry, created in the lifespan and injected via `BccClientsMapDep` /
`BccClientDep` (which resolves the `{backend}` path param and raises `UnknownBccError`).

Every outbound call goes through `BccClient._request`, which signs the request
(`x-mss-request-id`, `x-mss-timestamp`, `x-mss-signature`, `x-mss-user-id`, optional
`x-mss-is-admin`), raises `BccHttpError` with the status of a BCC error response, and
turns connection/timeout failures into `ServiceUnavailableError` → 503. Client methods:
`get_token`, `cancel_job`, `delete_job`, `view_users`, `create_user`, `delete_user`,
`create_booking`, `cancel_booking`, `view_bookings`, `view_bookings_configs`,
`init_recalibration`, `get_recalibration_info`, `stop_recalibration`, `switch_off`,
`switch_on`.

`services/external/email/` is the other outbound client: a thin `aiosmtplib` wrapper whose
only caller is the notification outbox sweeper (`services/notifications/outbox.py`). Nothing on
a request path sends mail, so a dead mail server cannot fail a request.

**Bookings and BCC users are not persisted by MSS.** The `/bookings` and
`/admin/bcc-users` routes proxy to the owning backend on the user's behalf. Only jobs,
devices, calibrations, notices and the auth entities live in MongoDB.

### Inbound: the device websocket

`WS /devices/ws/{name}` is how a backend pushes state. The handshake is verified by
`get_verified_device_name` (signature, source IP, nonce freshness, nonce replay) and the
socket is registered with a `WebsocketConnectionManager`. Each JSON frame is a
`DeviceEvent` dispatched through `_EVENT_HANDLER_MAP` in `api/rest/routers/devices/__init__.py`
to a handler in `events.py`:

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
enum member in `services/devices/dtos.py`, a handler in `events.py`, and an entry in
`_EVENT_HANDLER_MAP`.

## 5. Data

MongoDB, reached via motor. Two access styles coexist:

- **Beanie `Document`s** for the auth entities and notices — `auth_users`,
  `auth_projects`, `deleted_auth_projects`, `auth_app_tokens`, user requests, `notices`.
  Registered in `init_beanie` during startup; indexes declared in each `Settings` class.
- **Raw collections through `utils/mongodb.py`** for jobs, devices and calibrations —
  `find`, `find_one`, `insert_one_if_not_exists`, `update_one`, `update_many`,
  `delete_many`, each taking a Pydantic `schema=` to validate results into DTOs and raising
  `DbValidationError` on mismatch.

Notable collections: `jobs`, `devices`, `calibrations`, `calibrations_logs` (historical,
indexed on `(name, last_calibrated desc)`), `notices` (TTL index on `expires_at`).
Deleting a project moves it to `deleted_auth_projects` rather than dropping it.

**Redis** ([utils/redis_store.py](./utils/redis_store.py)) backs one thing: the
request-log store used for websocket nonce replay protection, entries expiring after
`request_log_ttl`. It is a small hand-rolled indexed-collection abstraction (`Schema` +
`Collection[T]`) over Redis hashes and sorted sets, not a general cache.

## 6. REST conventions

Codified in [docs/api-design.md](./docs/api-design.md); the short version:

- URLs are `/{resource}/({id})`. Every resource has a DTO named after it.
- List endpoints return `{"skip": int, "limit": int | null, "data": [...]}` — build it with
  `PaginatedListResponse` and `.model_dump(mode="json")`.
- Action endpoints return `{"status": ..., "message": ...}` (`GeneralMessage`).
- Errors return `{"detail": "..."}` with a non-2xx status — produced by the central handlers,
  not per-route try/except.
- List filtering is a Pydantic query model injected with `Depends()` (e.g. `JobQuery`,
  `DeviceQuery`), usually built by `create_partial_model` so every field is optional.
  `sort` is a repeated query param where a leading `-` means descending.
- Property-only sub-resources (e.g. `GET /jobs/{id}/status`) are allowed only when that
  property is requested far more often than the whole object, and return `{"{property}": …}`.

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

`pytest` with a real MongoDB and a real Redis — no database mocking. `tests/conftest.py`
calls `setup_test_env()` **before any app import**, because `settings.py` reads config at
import time; keep that ordering when adding fixtures.

- `tests/_utils/` — shared helpers, grouped by what they do: `auth.py`, `bcc.py`,
  `mongodb.py`, `fixtures.py`, `records.py`, `env.py`, `json.py`, `date_time.py`,
  `mock_backend.py`, `modules.py`, `numbers.py`, `types.py`. Put new helpers here, in the
  file that matches their job — not in a single `utils.py` and not in scattered
  `fixtures/*.py` modules.
- `tests/fixtures/` — JSON data and the RSA key pairs used to exercise the MSS↔BCC
  signature paths.
- `tests/api/rest/test_*.py` — one file per router, driven through `TestClient`.
- `mock_backend.py` stands in for BCC; `respx` intercepts httpx calls.
- The `db` fixture drops its database afterwards and `redis_client` flushes — tests must not
  assume a clean store beyond what those give them.

CI runs `black --check .` then `pytest` on Python 3.12 and 3.13.

## 8. Python style

On top of the shared rules in [../../DESIGN.md](../../DESIGN.md#style-guide):

- **`black` is authoritative** for formatting (pinned `black==23.11.0`, and the only CI
  gate); `isort` for imports, configured with `profile = "black"` so the two agree —
  without it isort emits a style black then reformats, churning unrelated files. Run both
  before committing; neither needs flags.
- **Constants go at the top of the file**, after imports — not buried between functions. The
  exception is a constant built from a function or class defined in the same file, which
  stays after it (e.g. `_EVENT_HANDLER_MAP` after the handler imports, `ProjectPartial`
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
- **Type hints everywhere**, including `async def` return types. DTOs are Pydantic models,
  never bare dicts crossing a service boundary.
- **License header** on every new file: copy the block from a neighbouring module and add
  the copyright line for the contributing party.

## 9. Adding things — where to start

| Task | Path |
| --- | --- |
| New endpoint on an existing resource | the router in `api/rest/routers/`, plus a service function; add a `tests/api/rest/test_*.py` case |
| New resource | new package under `services/` (`dtos.py` + `service.py`, `on_startup` if it needs indexes), new router module, include it in `api/rest/__init__.py` |
| New injectable | an `Annotated` alias in `api/rest/dependencies.py` |
| New OAuth2 provider | a `[[auth.clients]]` block — no code; see [docs/auth.md](./docs/auth.md) |
| New quantum backend | a `[[backends]]` block plus its public key — no code; see [docs/backends.md](./docs/backends.md) |
| New device event | enum member in `services/devices/dtos.py`, handler in `routers/devices/events.py`, entry in `_EVENT_HANDLER_MAP` |
| New config option | a field on the right model in `utils/config.py` **and** a documented entry in `mss-config.example.toml` |
| New BCC call | a method on `BccClient` using `self._request`, so signing and error mapping are inherited |
