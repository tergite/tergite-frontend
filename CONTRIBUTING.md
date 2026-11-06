# Contributing to tergite-frontend

**This project is currently not accepting pull requests from the general public yet.**

**It is currently being developed by the core developers only.**

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Government Model

[Chalmers Next Labs AB (CNL)](https://chalmersnextlabs.se) manages and maintains this project on behalf of all contributors.

## Version Control

Tergite is developed on a separate version control system and mirrored on Github.
If you are reading this on GitHub, then you are looking at a mirror.

## Contacting the Tergite Developers

Since the Github repositories are only mirrors, no Github pull requests or Github issue/bug reports
are looked. Please get in touch via email <quantum.nextlabs@chalmers.se> instead.

Take note that the maintainers may not answer every email.

## But We Use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow), So All Code Changes Happen Through Pull Requests

Pull requests are the best way to propose changes to the codebase (we
use [Github Flow](https://docs.github.com/en/get-started/quickstart/github-flow)). We actively welcome your pull
requests:

1. Clone the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Any contributions you make will be under the Apache 2.0 Software Licenses

In short, when you submit code changes, your submissions are understood to be under the
same [Apache 2.0 License](./LICENSE.txt) that covers the project. Feel free to contact the maintainers if that's a concern.

## Write bug reports with detail, background, and sample code

[This is an example](http://stackoverflow.com/q/12488905/180626).
Here's [another example from Craig Hockenberry](http://www.openradar.me/11905408).

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People _love_ thorough bug reports. I'm not even kidding.

## License

By contributing, you agree that your contributions will be licensed under its Apache 2.0 License.

## Contributor Licensing Agreement

Before you can submit any code, all contributors must sign a
contributor license agreement (CLA). By signing a CLA, you're attesting
that you are the author of the contribution, and that you're freely
contributing it under the terms of the Apache-2.0 license.

The [individual CLA](https://tergite.github.io/contributing/icla.pdf) document is available for review as a PDF.

Please note that if your contribution is part of your employment or
your contribution is the property of your employer,
you will also most likely need to sign a [corporate CLA](https://tergite.github.io/contributing/ccla.pdf).

All signed CLAs are emails to us at <contact.quantum@chalmersnextlabs.se>.

## How to Test

- Make sure you have [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, and
  [Node.js 26.12.1 or later](https://nodejs.org/) for the dashboard in `ui/`.
- Clone the repo and enter its root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Install MSS's dependencies, which uv puts in `.venv` as `uv.lock` pins them

```shell
uv sync --extra dev
```

- Run MSS's tests, which need the MongoDB that `tests/fixtures/config.test.toml` names,
  and the PostgreSQL that `TEST_POSTGRES_URL` does

```shell
uv run pytest
```

- Install the dashboard's dependencies, and run its tests

```shell
cd ui
npm i
npm run test
```

## How to Work on MSS

The [Quick Start](./README.md#quick-start) is all the dashboard needs. For MSS:

- Its settings are in `mss-config.toml`, which [mss-config.example.toml](./mss-config.example.toml)
  documents. Its `[database]` url may name a MongoDB or PostgreSQL instead of SQLite.
- Run MSS alone, without the test data and the dashboard's dev server:

```shell
uv run ./start_mss.sh
```

- To run jobs, run a [tergite-backend](https://github.com/tergite/tergite-backend) at the url of
  `[[backends]]` in `mss-config.toml`, and exchange public keys with it, as
  [docs/backends.md](./docs/backends.md) describes.

## How to Run End-to-end Tests

- Ensure you have [nodejs](https://nodejs.org/en), [uv](https://docs.astral.sh/uv/), MongoDB's
  `mongod` and `mongosh` and `sqlite3` installed
- Ensure nothing is running on ports 3001, 8002, 8101 and 27018
- Clone the repo, and tergite-backend beside it unless `BACKEND_REPO` is given

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Run the tests command

```shell
BACKEND_PATH="../tergite-backend" \
# BACKEND_REPO="https://github.com/tergite/tergite-backend.git" \ # cloned when BACKEND_PATH is not set
# BACKEND_BRANCH="main" \ # the branch of BACKEND_REPO to clone; default is 'main'
# DEBUG="True" \ # Set 'True' to keep the services running and temp-native/ after the tests, default: ''
# VISUAL="True" \ # Set 'True' to run the e2e in Playwright's UI mode, default: ''
./dev/e2e_native_test.sh
```

- It seeds MSS's database from [ui/fixtures/](./ui/fixtures), serves the dashboard's test build
  from MSS at `/ui`, and passes its arguments to `playwright test`, e.g. a spec to run alone:

```shell
BACKEND_PATH="../tergite-backend" ./dev/e2e_native_test.sh playwright/home.spec.ts
```

## How to Build

- Follow the first three steps of [How to Test](#how-to-test)
- Build the dashboard in `ui/` into `ui/dist`, which the build includes for MSS to serve at `/ui`;
  `npm run dev` empties `ui/dist`, so build again after it

```shell
(cd ui && npm ci && npm run build)
```

- Build the folder the packages install, `build/mss`: uv's own build of Python, with the
  dependencies `uv.lock` pins and MSS installed into it, the dashboard's build, and the `mss`
  that runs them, for this machine's OS and architecture, in a minute or two

```shell
pkg/build.sh
```

- After the build, the app is `build/mss/mss`, which runs the Python beside it. You can run it.

```shell
# create the mss-config.toml, a development config
cp mss-config.example.toml mss-config.toml
# create the mss private key, unencrypted as the development config expects
openssl genpkey -algorithm RSA -out private-mss-key.pem -pkeyopt rsa_keygen_bits:4096
# migrate the database, MongoDB or SQL, and run the app, with any of `--port`, `--host`,
# `--forwarded-allow-ips`, `--workers` and `--reload`; `build/mss/mss migrate` or `build/mss/mss serve` does one alone
MSS_CONFIG_FILE="$PWD/mss-config.toml" PRIVATE_KEY_FILE="$PWD/private-mss-key.pem" build/mss/mss start --port 8002
```

## How to Generate Snapshots for CI

Playwright names each screenshot baseline after the platform (`-chromium-darwin.png`,
`-chromium-linux.png`), so CI on linux needs the linux ones beside those made on a mac. Generate
them with the e2e stack in Playwright's own linux image, which has the browsers:

- Make sure you have [docker](https://docs.docker.com/engine/install/) installed.

- Clone the repo, and tergite-backend beside it, and enter the repo's root folder

```shell
git clone git@github.com:tergite/tergite-frontend.git
cd tergite-frontend
```

- Generate the image `tergite-dashboard-playwright`, with the repo's root as the context

```shell
docker build -t tergite-dashboard-playwright:latest -f ui/Dockerfile.playwright .
```

- Run the suite in it, with the backend and the specs' folder mounted, so that the new baselines
  land in it

```shell
docker run --rm -v "$PWD/../tergite-backend:/backend" -e BACKEND_PATH=/backend \
  -v "$PWD/ui/playwright:/repo/ui/playwright" \
  tergite-dashboard-playwright:latest
```

- The new baselines are the `-chromium-linux.png` files in the `ui/playwright/*-snapshots/`
  folders; commit them if anything has changed

```shell
git add ui/playwright
git commit -m "Updated the baseline snapshots for end-to-end tests"
```

## Where the Tests Are

| Level | Where | Command |
| --- | --- | --- |
| MSS | `tests/`, pytest against real MongoDB, PostgreSQL and SQLite | `uv run pytest` |
| Dashboard components | `ui/src/**/__tests__`, vitest with happy-dom | `npm run test` |
| End-to-end | `ui/playwright`, Playwright against MSS and real backends, all running natively | `BACKEND_PATH=../tergite-backend ./dev/e2e_native_test.sh` |

### MSS's tests

- `tests/conftest.py` calls `setup_test_env()` **before any app import**, because `settings.py`
  reads the config when imported. Keep that order when adding fixtures.
- `tests/api/test_*.py` has one file per router, driven through `TestClient`.
  `tests/_utils/mock_backend.py` stands in for a backend, and `respx` intercepts httpx calls.
- `tests/_utils/` holds the shared helpers, one file per kind (`auth.py`, `bcc.py`,
  `storage.py`, `fixtures.py`, …). Put new helpers there, in the file that matches their job.
- `tests/fixtures/` holds JSON data and the key pairs for the MSS–backend signatures.
- The app starts once per session, as its startup is the slow part. A fixture that changes
  what the app starts with (`unconfigured_email`) is listed in `_FRESH_APP_FIXTURES`, and its
  test gets a freshly started app.
- The storage tests run on MongoDB, PostgreSQL and SQLite; the API tests run once, on the
  database `TEST_DATABASE_URL` names (the test config's MongoDB if unset). The `db` fixture
  empties every table afterwards, except the roles and notice templates the app writes at
  startup. Don't assume a cleaner store than that.

### The end-to-end tests

`dev/e2e_native_test.sh` runs the whole stack from fresh data in `temp-native/`, so it catches
contract drift between the repos:

- tergite-backend from a local checkout, or a clone of the branch or tag of this one's name,
  else its newest release of the same month, else `main`; one `main.py serve` for all the
  backends;
- MSS from this checkout, serving the dashboard's test build at `/ui`, seeded from
  `ui/fixtures/*.json` by `dev/seed.py`, with a stand-in OpenID provider;
- its own MongoDB, and a reset server (`dev/e2e_reset_server.py`).

The Playwright specs run on one worker, as they share data; a test that wrote has the next
reset it through `GET /refreshed-db`. Visual regression uses `toHaveScreenshot`, whose
baselines are per platform: see [How to Generate Snapshots for CI](#how-to-generate-snapshots-for-ci).

## Before a Merge Request

- `uv run ruff format --check`, `uv run ruff check` and `uv run pytest`;
- in `ui/`, `npm run lint`, `npm run check:api` and `npm run test`;
- the end-to-end tests, for anything that crosses MSS, the dashboard and a backend.

CI (GitLab, mirrored by GitHub Actions) runs these on every merge request, on `main` and on `v*`
tags: ruff and pytest on Python 3.13 against MongoDB and PostgreSQL; eslint,
`npm run check:api` and vitest; then the end-to-end tests. On a `v*` tag it also builds the
dashboard, then MSS's deb and macOS installer, and attaches them to the release; GitLab's macOS
job runs only where `PUBLISH_MACOS_ARM64` is `true`.

## Where to Start

| Task | Where |
| --- | --- |
| New endpoint on an existing resource | the router in `api/routers/`, a service function, and a `tests/api/test_*.py` case; see [docs/api-design.md](./docs/api-design.md) |
| New resource | a package under `services/` (`dtos.py` and `service.py`, `on_startup` if it needs config), a router module, included in `api/__init__.py` |
| New injectable | an `Annotated` alias in `api/dependencies.py`, ending in `Dep` |
| New table or field | a `Schema` in the service's `dtos.py`, and a migration; see [docs/storage.md](./docs/storage.md) |
| New OAuth2 provider | a `[[auth.clients]]` block, no code; see [docs/auth.md](./docs/auth.md) |
| New quantum backend | a `[[backends]]` block and its public key, no code; see [docs/backends.md](./docs/backends.md) |
| New device event | see [docs/backends.md](./docs/backends.md#adding-or-changing-an-event) |
| New config option | a field on the right model in `utils/config.py` **and** a documented entry in `mss-config.example.toml` |
| New call to a backend | a method on `BccClient` using `self._request`, which signs it and maps its errors |
| Anything in the dashboard | [ui/DESIGN.md](./ui/DESIGN.md) |

Read [DESIGN.md](./DESIGN.md) first for how the code is laid out.

## Conventions

MSS and the dashboard share the style guide and code structure below. Their layouts differ on
purpose: MSS is organised by service ([DESIGN.md](./DESIGN.md#code-map)), the dashboard by a
co-located page hierarchy ([ui/DESIGN.md](./ui/DESIGN.md)). Read the relevant one before adding
files.

### Style Guide

- **Comments and docstrings must earn their place.** Say the constraint, the gotcha, the *why*
  the code cannot. Never restate the code, never narrate the history of a fix. Default to none.
- **Names**: variables are nouns, functions are verbs, booleans start with `is_`/`should_`.
  If the name alone does not say what it returns, rename it.
- **No banner comments** (`# --- section ---`, `// ==== section ====`) at any indent. A group
  that needs a label needs a docstring or its own file.
- **Tests**: the name says what it tests. Add a comment only when the *why* is not obvious.
- **License headers**: every Python file in MSS carries the Tergite Apache-2.0 header, with a
  copyright line per contributing party. Dashboard TypeScript files have none.

### Code Structure

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
   tooling (scripts, generators, performance checks, the seeding) lives in `dev/`; the other
   folders hold the app and its tests, so the tree shows the architecture and nothing else.
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
13. **No request writes what nothing reads.** An HTTP request is not recorded: its id is
    only echoed and signed into calls to BCC, whose own nonce table refuses a replay. Writing
    every request to MongoDB doubled p95 latency.
14. **A value that is only defined stays where it is used.** A function that does no more than
    return a literal (a dict, a filter, an update, a range) makes the reader jump to it and
    back for nothing; write the literal at its use, in an `if`/`else` where it varies.
    Functions of their own are for real actions, such as I/O, a check that raises, or a
    computation with steps; the one-liner exception above covers the rest.

### Python Style

- **`ruff format` and `ruff check` are authoritative**; CI fails on any finding. `ruff format`
  and `ruff check --fix` fix what they find.
- **Constants at the top** of the file, after the imports, except one built from a function or
  class of the same file, which stays after it (`EVENT_HANDLERS` after the handlers).
- **Module-private helpers** (`_name`) at the **bottom**, unless definition order forces
  otherwise.
- **Docstrings**: one line where one line does; Google style (`Args:`, `Returns:`, `Raises:`,
  with the messages callers can expect) where a function takes several arguments or raises
  domain exceptions.
- **Type hints everywhere**, `async def` return types included. DTOs are Pydantic models, never
  bare dicts across a service boundary.

### Commits and Changelog

- One logical change per commit.
- Every change users or operators notice gets a [CHANGELOG.md](./CHANGELOG.md) entry under
  `[Unreleased]`, in `Added`/`Changed`/`Fixed`: one or two sentences on what changed and what an
  operator would have hit before. The reasoning goes in the commit body.

### Releases

Versions are `{year}.{month}.{patch}`, e.g. `2026.06.0`. A release bumps the version in four
places and dates the `[Unreleased]` section of the changelog:

- `pyproject.toml` and `api/app_kwargs.py`;
- `ui/package.json` and `ui/package-lock.json`.

## References

This document was adapted from [a gist by Brian A. Danielak](https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62) which
was originally adapted from
the open-source contribution guidelines
for [Facebook's Draft](https://github.com/facebook/draft-js/blob/a9316a723f9e918afde44dea68b5f9f39b7d9b00/CONTRIBUTING.md)
