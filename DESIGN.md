# Tergite Frontend — System Design

This document describes the architecture of the `tergite-frontend` monorepo: what the two
apps are, how they talk to each other and to the rest of the Tergite stack, how the repo
is configured, built, deployed and tested, and the conventions a contributor is expected
to follow.

Per-app design documents:

- [apps/tergite-mss/DESIGN.md](./apps/tergite-mss/DESIGN.md) — the REST API server (service-oriented layout)
- [apps/tergite-dashboard/DESIGN.md](./apps/tergite-dashboard/DESIGN.md) — the web UI (co-located page hierarchy)

## 1. What this repo is

`tergite-frontend` is the user-facing half of the [Tergite stack](https://tergite.github.io/)
for the WACQT quantum computers. It is a monorepo of two applications that were originally
developed as separate repositories and later merged under `apps/`. They are still built and
tested independently in CI, and released together: MSS's deb and macOS installer carry the
dashboard's build, which MSS serves at `/ui`. They share this repo, the `mss-config.toml`
configuration file, the end-to-end test harness, and the release tag.

| App | Path | Stack | Role |
| --- | --- | --- | --- |
| **MSS** (Main Service Server) | `apps/tergite-mss` | Python 3.12+, FastAPI, MongoDB, Redis | The public REST API. Owns all persistence, authn/authz, and all traffic to the quantum backends. |
| **Dashboard** | `apps/tergite-dashboard` | Node 20, Vite, React 18, TypeScript, Tailwind + shadcn/ui | The browser client for MSS. No backend of its own — it is a static bundle MSS serves at `/ui`. |

Everything the dashboard shows comes from MSS, which knows the dashboard only as the files
it serves at `/ui`.

## 2. System context

```mermaid
flowchart LR
    subgraph clients [Clients]
      SDK["tergite SDK<br/>(Python, app token)"]
      Browser["Browser<br/>(dashboard, cookie)"]
    end

    subgraph frontend ["tergite-frontend (this repo)"]
      MSS["tergite-mss<br/>uvicorn :80 → :8002"]
      Mongo[("MongoDB")]
      Redis[("Redis<br/>request-log store")]
    end

    subgraph backends ["Quantum backends (separate repos)"]
      BCC1["tergite-backend / BCC #1"]
      BCC2["tergite-backend / BCC #2"]
    end

    IdP["OAuth2 / OpenID providers<br/>(Chalmers, GitHub, Okta, …)"]
    Loki["Grafana Loki<br/>(via grafana-alloy)"]

    Browser -->|"/ui, REST + cookie"| MSS
    SDK -->|"REST + Bearer app token"| MSS
    MSS --> Mongo
    MSS --> Redis
    MSS <-->|"signed HTTP"| BCC1
    MSS <-->|"signed HTTP"| BCC2
    BCC1 -->|"websocket events"| MSS
    BCC2 -->|"websocket events"| MSS
    MSS -->|"OAuth2 redirect flow"| IdP
    frontend -.->|"journal, via Grafana Alloy"| Loki
```

MongoDB, or PostgreSQL, and Redis are reached via `database.url` and `database.redis_url` in
`mss-config.toml`; MSS's deb installs and provisions them alongside it on Debian and Ubuntu.

## 3. The two apps, and the seam between them

### 3.1 Contract

The dashboard depends on MSS only through:

1. **HTTP JSON endpoints** — every call goes through the openapi-fetch client in
   [src/lib/api/client.ts](apps/tergite-dashboard/src/lib/api/client.ts), which always sends
   `credentials: "include"`. The base URL is the build-time `VITE_API_BASE_URL`, empty in the
   production build, which calls MSS on the origin that served it.
2. **The auth cookie** — MSS sets a JWT cookie whose name and domain come from
   `auth.cookie_name` / `auth.cookie_domain` in `mss-config.toml`, which the browser sends
   with every call, as the dashboard and the API share MSS's origin.
3. **The OpenAPI schema** — MSS commits it as `apps/tergite-mss/dev/openapi/openapi.json`,
   and the dashboard's `npm run generate:api` regenerates both it and the TypeScript types
   in `src/lib/api/schema.d.ts` that type the client, so a change to an MSS route or DTO
   fails the dashboard's `tsc`. The mock API fixtures still follow by hand.

The classic misconfiguration is `localhost` vs `127.0.0.1`: the cookie domain and the host
you type in the browser must match, or login appears to succeed and then bounces back to
`/login`.

### 3.2 Job submission — the one flow that crosses everything

```mermaid
sequenceDiagram
    participant C as Client (SDK)
    participant M as MSS
    participant D as MongoDB
    participant B as BCC (backend)

    C->>M: POST /jobs (Bearer app token)
    M->>M: resolve project from token, check qpu_seconds > 0
    M->>D: insert job (new job_id)
    M->>B: POST /token (x-mss-signature, signed with MSS private key)
    B->>B: verify signature against MSS public key, mint user token
    B-->>M: token encrypted with MSS public key
    M->>M: decrypt token
    M-->>C: { job_id, upload_url, token }
    C->>B: POST job payload to upload_url (Bearer token)
    B-->>M: websocket "job_updated" events → /devices/ws/{name}
    M->>D: update job, decrement project qpu_seconds
```

Two distinct trust directions, both asymmetric-key based:

- **MSS → BCC**: MSS signs `"{user_id}-{request_id}-{timestamp}"` with its private key
  (`PRIVATE_KEY_FILE`) and sends `x-mss-*` headers. See `_create_headers` in
  [services/external/bcc/service.py](apps/tergite-mss/services/external/bcc/service.py).
- **BCC → MSS**: on the websocket handshake BCC sends `x-id`, `x-request-id`, `x-timestamp`,
  `x-signature`; MSS verifies against that backend's `public_key_path`, checks the source IP
  (unless `is_strict_ip = false`), rejects stale nonces (`bcc_nonce_ttl`) and replayed ones
  (the request log in Redis, where a nonce is the key). See `get_verified_device_name` in
  [api/utils.py](apps/tergite-mss/api/utils.py).

## 4. Configuration

There are three configuration surfaces, and they overlap deliberately.

### 4.1 `mss-config.toml` (MSS)

Copy [apps/tergite-mss/mss-config.example.toml](apps/tergite-mss/mss-config.example.toml) →
`mss-config.toml`, or let the deb's provisioning write `/etc/tergite-mss/mss-config.toml`.
Sections: `[general]`, `[database]`, `[[backends]]` (one per BCC), `[projects]`, `[notices]`,
`[email]`, `[auth]` and `[[auth.clients]]` (one per OAuth2 provider). MSS reads the file
`MSS_CONFIG_FILE` names, or the JSON in `MSS_CONFIG_JSON_STR` when it is set;
the app validates it into `AppConfig`
([utils/config.py](apps/tergite-mss/utils/config.py)) at import time in `settings.py` and
fails fast on anything missing.

The file may be SOPS-encrypted with a Hashicorp Vault key; `start_mss.sh` detects this and
decrypts it into `MSS_CONFIG_JSON_STR` using `VAULT_ADDR` / `VAULT_TOKEN` from the environment.

### 4.2 `.env*` files in the dashboard

Vite conventions. `VITE_`-prefixed variables are baked into the bundle at build time —
they are not runtime configuration. `.env.production` empties `VITE_API_BASE_URL`, so the
build MSS serves calls its own origin. `.env.development` / `.env.test` also carry
`JWT_SECRET` and `AUTH_AUDIENCE` used only by the mock API server.

## 5. Deployment

MSS installs from its release's deb (amd64, Debian 13 and Ubuntu 24.04 onwards) or macOS arm64
installer, Nuitka's standalone build running as the `tergite-mss` systemd service or launchd daemon on
`8002`. The deb asks debconf where the database and Redis are, and its provisioning writes
`/etc/tergite-mss/mss-config.toml` and the private key; on macOS the config is written by hand
to `/usr/local/etc/tergite-mss/`. See the [README](README.md#deployment).

The dashboard ships inside MSS's packages: the release builds it with the base `/ui/`, Nuitka
includes it from `apps/tergite-mss/ui/`, and MSS serves it at `/ui`
([api/dashboard.py](apps/tergite-mss/api/dashboard.py)), sending the paths no file
has to `index.html` and redirecting `/` to `/ui/`.

MSS answers `GET /health` with 200 outside the request log, as `RequestIDMiddleware`
skips it, so that a frequent probe does not bury real traffic.

Logs reach Loki through Grafana Alloy installed beside MSS, whose [config.alloy](config.alloy)
reads `tergite-mss.service`'s journal and pushes it with `GRAFANA_LOKI_URL` and `LOKI_LOGGER_ID`.

## 6. Testing

| Level | Where | Command |
| --- | --- | --- |
| MSS unit/integration | `apps/tergite-mss/tests` — pytest against real MongoDB + Redis | `pytest` |
| Dashboard component | `apps/tergite-dashboard/src/**/__tests__` — vitest + happy-dom | `npm run test` |
| Dashboard e2e | `apps/tergite-dashboard/playwright` — Playwright against the **mock** API, a mock API per worker | `npm run e2e` |
| Full-stack e2e | [dev/e2e_native_test.sh](dev/e2e_native_test.sh) — the same Playwright specs against real MSS + real backends, with MongoDB and Redis, all running natively | `BACKEND_PATH=../tergite-backend ./dev/e2e_native_test.sh` |

The dashboard's own e2e suite does not run MSS. It runs an Express mock API
(`apps/tergite-dashboard/dev/mock-api/`) that serves the same JSON shapes from
`apps/tergite-dashboard/fixtures/*.json`, plus a
`GET /refreshed-db` endpoint tests hit to reset state.
This keeps the UI suite fast and deterministic, at the cost of a second place to update
when an MSS response changes.

`dev/e2e_native_test.sh` is the one that catches contract drift: from a local
`tergite-backend` checkout or a clone, it runs one `main.py serve` for all the backends, each
under its own path, from the base dependencies, MSS from this checkout, the dashboard's test
build, and a MongoDB, a Redis and a reset service (`dev/e2e_reset_server.py`) of its own, all
from fresh data in `temp-native/`; it seeds Mongo from the same fixtures, wires up a mock
OpenID provider, and runs the Playwright specs against that stack, on one worker. It is a
manual / tag-triggered job in CI, not a per-commit one.

Visual regression is Playwright's `toHaveScreenshot`; its baselines are named after the
platform, so make the Linux ones through the dashboard's `Dockerfile.playwright` (see its
`CONTRIBUTING.md`).

## 7. CI

Both GitHub Actions ([.github/workflows](.github/workflows)) and GitLab CI
([.gitlab-ci.yml](.gitlab-ci.yml)) are maintained; GitLab is the source of truth (GitHub is
a mirror — see §8).

- `mss-ci.yml` / `test mss` — `black --check .`, `pyflakes`, then `pytest` on Python 3.12 and
  3.13 against `mongo` and `redis` services. Path-filtered to `apps/tergite-mss/**`.
- `dashboard-ci.yml` / `lint dashboard`, `test dashboard`, `e2e test dashboard` —
  eslint and `npm run check:api`, vitest, Playwright. Path-filtered to
  `apps/tergite-dashboard/**` and MSS's `dev/openapi/openapi.json`.
- `frontend-ci.yml` / `full e2e` — the cross-app `dev/e2e_native_test.sh`, after installing
  MongoDB, Redis, SQLite and uv, on `main`, on `v*` tags, or manually.
- On a `v*` tag, `mss-release.yml` / `build dashboard`, `package mss linux`, `package mss macos`
  and `release` build the dashboard, then MSS's deb and macOS installer with it, and attach
  them to the release. GitLab's jobs upload them to the project's package registry and link
  them from its release; its macOS job runs only where `PUBLISH_MACOS_ARM64` is `true`, on a
  runner tagged `macos`.

## 8. Working on this repo

### Version control

Tergite is developed on a private GitLab and **mirrored to GitHub**. GitHub PRs and issues
are not read. Contributions and bug reports go to <contact.quantum@chalmersnextlabs.se>;
code changes need a signed CLA. See [CONTRIBUTING.md](CONTRIBUTING.md).

### Versioning and releases

`{year}.{month}.{patch}`, e.g. `2026.06.0`. A release bumps the version in **four** places
and touches **three** changelogs:

- `apps/tergite-mss/pyproject.toml` and `apps/tergite-mss/api/app_kwargs.py`
- `apps/tergite-dashboard/package.json` and `package-lock.json`
- `CHANGELOG.md`, `apps/tergite-mss/CHANGELOG.md`, `apps/tergite-dashboard/CHANGELOG.md`

### Changelog entries

One or two sentences: what changed, and what an operator would have hit before. Always
under `[Unreleased]`, under `Added` / `Changed` / `Fixed` as the file already uses them.
Reasoning, alternatives and numbers belong in the commit body, not the changelog.

### Commits

One logical change per commit, decided before editing rather than carved out of a large
working tree afterwards. Never add assistant attribution (`Co-Authored-By`, "Generated
with", …) to commit messages or MR bodies.

### Style guide

Shared across both apps:

- **Comments and docstrings must earn their place.** Say the constraint, the gotcha, the
  *why* that the code cannot. Never restate the code, never narrate the history of a fix —
  that is what the commit message is for. Default to none.
- **Names**: variables are nouns, functions are verbs, booleans start with `is_`/`should_`.
  If the name alone does not say what it returns, rename it.
- **No banner comments** (`# --- section ---`, `// ==== section ====`) at any indent. If a
  group needs a label it needs a docstring or its own file.
- **Tests**: the name says what it tests. Add a line of comment only when the *why* is
  non-obvious.
- **License headers**: every Python file in MSS carries the Tergite copyright/Apache-2.0
  header, with a line added per contributing party. Keep this when creating new modules.
  Dashboard TypeScript files do not carry per-file headers.

Language- and layout-specific rules — MSS's service-oriented layout and Python
conventions, the dashboard's co-located page hierarchy and React/TypeScript conventions —
are in each app's design document (§1). **Read the relevant one before adding files**; the
two apps deliberately organise code in different ways and the difference is load-bearing.

### Code structure

Code reads like an article: the overview first, the detail below it. New code follows these
rules, and code a change touches is brought in line with them.

1. **A function is a composition of functions.** A public function's body is a short sequence
   of calls, each to a function that does one thing and is named for it. A reader gets the
   whole flow from that body and drills into a step only when they need its detail. Each step
   is built the same way until it is a single operation.
2. **Two exceptions.** Do not extract a step that would be a one-line function. Do not split a
   performance-critical path where the extra calls cost something measurable.
3. **Callees sit below their callers.** A file runs: constants, public functions in the order a
   caller uses them, then private helpers in the order they are first called. Reading top-down
   follows the drill-down.
4. **A comment that labels a phase is a missing function.** `# Authenticate` or `# route to
   generate tokens` becomes the name of the function that does it.
5. **Data is a struct; state gets a class.** Data is a Pydantic model, a frozen `@dataclass`,
   an `Enum` or an `Exception` (a `type` in TypeScript); its only methods are derived views of
   its own fields, such as `Project.members`, and conversions to or from another shape, named
   `from_*` or `to_*` (`Notice.from_template`, `CustomNoticeCreate.to_documents`,
   `AppConfig.from_json_str`), even when a conversion reads the database to fill itself in. A
   component that owns state across calls (a connection pool, live sockets, background tasks)
   is a class with behaviour. Which is which is a judgement made by asking what the object
   holds between calls.
6. **Stateless behaviour is a module-level function.** It takes explicit arguments and returns
   data, with the `Database` first when it does I/O. Avoid the indirection that imitates state
   without holding any: objects built per request only to carry other objects, a `Protocol` or
   ABC with one implementation, inheritance used to share behaviour.
7. **Dependencies arrive as arguments.** A function or class never reads a global, in its body
   or as a default argument: config values, clients and keys are passed in, and the call site
   says what it passes. Only the composition root (`api`: the lifespan and the dependencies)
   reads `settings`, and it turns config into instances before handing them on: code that needs
   storage is given the `Database` instance, never a URL or a config section to build one from.
   The one exception is a module caching its own private global, such as a loaded key.
8. **One home per kind of thing.** Routes live in `api/routers/`. `HTTPException` is raised
   only in `api/`. Domain errors subclass `utils/exc.py` and are mapped to status codes once. A
   service's `__init__.py` only re-exports, with `__all__` as strings. Development and test
   tooling (scripts, generators, performance checks, the mock API) lives in a `dev/` folder:
   the repository's for tooling that spans both apps, an app's own for tooling only it uses. An
   app's other folders hold the app and its tests, so the tree shows the architecture and
   nothing else.
9. **A reputable library beats our own code.** Every line we write is a line to maintain and a
   line a newcomer reads. Use a well-maintained library wherever it does the job, and write our
   own only where none does, or where getting the behaviour we need would mean fighting the
   library. The commit that adds our own code says which of the two it was.
10. **A name says what the thing is.** Variables are nouns that name their content:
    `notice_filter`, never `where`, `kind` or `changes` for a filter. No function is named
    `build_*`: a thing that is constructed is a class's constructor, and anything else is got,
    so the function is a `get_*`. `tests/test_styleguide.py` does not count `build` as a verb.
11. **Obvious beats clever.** Write code a reader takes in at a glance: an `if`/`else` that
    returns each whole literal, one explicit `if` per optional field. Do not make the reader
    assemble the result in their head from a loop over tuples of fields, a comprehension that
    builds operators, merged dicts, or one helper that returns two things to be pulled apart. A
    helper that two callers share is fine when it reads the same way.
12. **Storage is queried in MongoDB's own dialect**: `filter={"user_id": {"$in": [user_id,
    None]}}`, `update={"$set": {...}}`, `sort=["-created_at"]`, `skip`, `limit`, never structs
    that wrap each operator. A service function takes its query's arguments or its query model
    and gets its filter privately; a route never makes one.
13. **What every request reads or writes lives in a cache.** The request log is in Redis,
    behind a `Database` of its own; records stay in the records' database. Putting per-request
    data in MongoDB doubled p95 latency.
14. **A value that is only defined stays where it is used.** A function that does no more than
    return a literal (a dict, a filter, an update, a range) makes the reader jump to it and
    back for nothing; write the literal at its use, in an `if`/`else` where it varies.
    Functions of their own are for real actions, such as I/O, a check that raises, or a
    computation with steps; the one-liner exception above covers the rest.

### Slow commands

Redirect test suites, builds and e2e runs to one temp file per kind of run, then grep and
tail that file for follow-up questions instead of re-running:

```bash
pytest > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"
```

Record the exit status next to the command — a pipe reports the *pipe's* status, so
`pytest | tail` makes a failing suite read as green. Never call a suite passing because a
grep found nothing; confirm from the summary line or the recorded status.

## 9. Known rough edges

Worth knowing before you are surprised by them:

- **No realtime backend liveness.** A device is "online" because it said so over the
  websocket; if BCC dies without disconnecting cleanly, MSS keeps showing it online until
  the socket drops. Called out in
  [apps/tergite-mss/docs/backends.md](apps/tergite-mss/docs/backends.md) and the root TODO.
- **503 handling in the dashboard is incomplete** (root `README.md` TODO).
- **`GET /counts/job-submitters` raises `NotImplementedError`.**