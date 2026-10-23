# Refactor plan

Eleven steps, in order. Each numbered item is one commit, verified before the next. Step 6 can start once step 3 lands. Step 9 (the dashboard) can run in parallel with MSS once step 1 and step 2.8 land.

## Conventions

The code reads like an article: the overview first, the detail below it. Every step in this plan applies these rules to the code it touches.

1. **A function is a composition of functions.** A public function's body is a short sequence of calls, each to a function that does one thing and is named for it. A reader gets the whole flow from that body and drills into a step only when they need its detail. Each step is built the same way until it is a single operation.
2. **Two exceptions.** Do not extract a step that would be a one-line function. Do not split a performance-critical path where the extra calls cost something measurable.
3. **Callees sit below their callers.** A file runs: constants, public functions in the order a caller uses them, then private helpers in the order they are first called. Reading top-down follows the drill-down.
4. **A comment that labels a phase is a missing function.** `# Authenticate` or `# route to generate tokens` becomes the name of the function that does it.
5. **Data is a struct; state gets a class.** Data is a Pydantic model, a frozen `@dataclass`, an `Enum` or an `Exception` (a `type` in TypeScript); its only methods are derived views of its own fields, such as `Project.members`. A component that owns state across calls (a connection pool, live sockets, background tasks) is a class with behaviour. Which is which is a judgement made by asking what the object holds between calls.
6. **Stateless behaviour is a module-level function.** It takes explicit arguments and returns data, with the `Database` first when it does I/O. This plan removes the indirection that imitates state without holding any: objects built per request only to carry other objects, a `Protocol` or ABC with one implementation, inheritance used to share behaviour.
7. **Dependencies arrive as arguments.** A function or class never reads a global, in its body or as a default argument: config values, clients and keys are passed in, and the call site says what it passes. Only the composition root (`api/rest`: the lifespan and the dependencies) reads `settings`, and it turns config into instances before handing them on: code that needs storage is given the `Database` instance, never a URL or a config section to build one from. The one exception is a module caching its own private global, such as a loaded key.
8. **One home per kind of thing.** Routes live in `api/rest/routers/`. `HTTPException` is raised only in `api/rest/`. Domain errors subclass `utils/exc.py` and are mapped to status codes once. A service's `__init__.py` only re-exports, with `__all__` as strings. Development and test tooling (scripts, generators, performance checks, the mock API) lives in a `dev/` folder: the repository's for tooling that spans both apps, an app's own for tooling only it uses. An app's other folders hold the app and its tests, so the tree shows the architecture and nothing else.
9. **A reputable library beats our own code.** Every line we write is a line to maintain and a line a newcomer reads. Use a well-maintained library wherever it does the job, and write our own only where none does, or where getting the behaviour we need would mean fighting the library. The commit that adds our own code says which of the two it was.
10. **Unchanged from `DESIGN.md`:** the Apache 2.0 licence header on every file, constants at the top, no banner comments, nouns for variables, verbs for functions, `is_`/`should_` for booleans, comments only for what the code cannot say.
11. **A name says what the thing is.** Variables are nouns that name their content: `notice_filter`, never `where`, `kind` or `changes` for a filter. No function is named `build_*`: a thing that is constructed is a class's constructor, and anything else is got, so the function is a `get_*`. `tests/test_styleguide.py` does not count `build` as a verb.
12. **Obvious beats clever.** Write code a reader takes in at a glance: an `if`/`else` that returns each whole literal, one explicit `if` per optional field. Do not make the reader assemble the result in their head from a loop over tuples of fields, a comprehension that builds operators, merged dicts, or one helper that returns two things to be pulled apart. A helper that two callers share is fine when it reads the same way.
13. **Storage is queried in MongoDB's own dialect** (step 3): `filter={"user_id": {"$in": [user_id, None]}}`, `update={"$set": {...}}`, `sort=["-created_at"]`, `skip`, `limit`, never structs that wrap each operator. A service function takes its query's arguments or its query model and gets its filter privately; a route never makes one.
14. **What every request reads or writes lives in a cache.** The request log is in Redis, behind a `Database` of its own; records stay in the records' database. Putting per-request data in MongoDB doubled p95 latency in step 3.
15. **A value that is only defined stays where it is used.** A function that does no more than return a literal (a dict, a filter, an update, a range) makes the reader jump to it and back for nothing; write the literal at its use, in an `if`/`else` where it varies. Rule 1's functions are for real actions, such as I/O, a check that raises, or a computation with steps; rule 2's one-liner exception covers the rest.

Rule 1 applied to `requests.update`, 94 lines today (signatures illustrative):

```python
async def update_request(database: Database, request_id: Id, approver: User, decision: RequestUpdate) -> Request:
    request = await _find_pending_for_approver(database, request_id, approver)
    decided = await _record_decision(database, request, approver, decision)
    await _clear_approver_notices(database, decided)
    await _notify_requesters(database, decided)
    return decided
```

**Every commit is verified the same way.** MSS: `black` and `isort` with no flags, then `pytest > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"`. Dashboard: `eslint`, `tsc`, `vitest`, `cypress`. `DESIGN.md` changes in the same commit as any file it names. `dev/e2e_test.sh` runs at the end of steps 7 and 9. The style rules a parser can see are tests too: `apps/tergite-mss/tests/test_styleguide.py` and `apps/tergite-dashboard/src/__tests__/styleguide.test.ts`, each with a baseline of the violations that existed when it was added. A commit that fixes a listed violation deletes its line from that baseline, and a commit may never add one.

**Every step ends with a sign-off.** Its last commit adds `docs/prototypes/<NN>-<step>.md`, a user acceptance test (UAT) script: how to start the app, what to do, and what should be seen. A user or an agent runs it, reruns the step 1.7 performance checks, and gives the go-ahead before the next step starts.

## Step 0: fix the bugs

The only behaviour changes in the plan. Each commit adds a test that fails before the fix and gets a `Fixed` changelog entry.

1. `api/rest/routers/calibrations.py:33, 64` have no auth dependency, though `DESIGN.md` said they need an app token. Decided: they stay open, like `/devices`, as public device data; `DESIGN.md` is corrected.
2. `api/rest/routers/jobs.py:87`: `GET /jobs/{id}` returns the decrypted BCC access token for any job to any active project. Decided: job reads (the job, its status, the list) go to the user who submitted it or an admin, whatever the project; a job stored without a submitter stays readable by anyone.
3. `api/rest/routers/counts.py:76`: `GET /counts/job-submitters` raises `NotImplementedError` (a 500). Decided: implement it for admins only, counting distinct submitters in the window, or every submission with `count_distinct=false`.
4. `utils/exc.py`: map `InvalidRequestIDError` to 400; it is a 500 today.
5. `dashboard/src/lib/app-state.ts:17`: `clear()` calls the factory's own no-op setters, so logout keeps the project and token. Call the real setters.
6. `dashboard/src/router.tsx:41`: the router is rebuilt on every render, remounting the tree on any app-state change. Fixed structurally in step 9.4; until then, memoise it.
7. `dashboard/src/lib/utils.ts:72, 76` and `calibration-map-chart.tsx:37`: numbers sort as strings, and the median index uses the unfiltered length. Sort with `(a, b) => a - b`; take the length of the filtered list.
8. Six dashboard pages, e.g. `tokens/index.tsx:38`: selection is by row index, so a reordering refetch selects the wrong item. Pass `getRowId: (row) => row.id` to `DataTable`.
9. `dashboard/api/utils.ts:284`: the mock's uniqueness check builds `{ k: payload[k] }` with a literal key. Use `[k]`.
10. `dashboard/src/router.tsx:70, 181`: the top-level `errorElement` renders `ErrorAlert`, which calls `useErrorBoundary()` outside a boundary. Reproduce first; fixed structurally in step 9.4.

## Step 1: pin behaviour with tests

Tests only. After this step, any refactor commit that changes behaviour fails a test.

1. **Auth contract.** Every row below has a test in `test_auth.py`, `me/test_my_tokens.py`, `admin/test_projects.py` or, for the rows they missed, `test_auth_contract.py`. Steps 5 and 7 must keep every row.

| Surface | Behaviour |
| --- | --- |
| Session JWT | HS256; claims `sub`, `aud`, `roles`; audience `["fastapi-users:auth"]`, which the dashboard mock API and live cookies rely on |
| OAuth state | JWT, audience `fastapi-users:oauth-state`, one-hour lifetime, `next` claim |
| Login | cookie `auth.cookie_name` on `auth.cookie_domain`, `max_age = jwt_ttl`, `httponly`, `secure`, `samesite=lax`; 204, or a redirect to `next` that carries the cookie |
| Logout | active and verified user required; cookie cleared; `{"message": "logged out"}` |
| `POST /me/tokens/` | `{"access_token": …, "token_type": "bearer"}`; `DELETE` returns 204 |
| User dependencies | missing or bad token → 401; inactive user → 401; superuser required → 403 |
| Project dependencies | missing, bad or expired token, or inactive project → 401; strict or system rule with `qpu_seconds <= 0` → 403 "{n} QPU seconds left on project {name}"; system rule without the role → 403 (no route uses the system rule today, so step 5.3's `test_access.py` pins it) |
| Invalid project id in a path | 404, not 422 |
| `auth_users` documents | `oauth_accounts` keeps its seven fields; existing documents load unchanged |

2. **Response bodies** for the routes whose DTOs override `model_dump`: jobs, devices, every paginated list. Already pinned: `test_jobs.py`, `test_devices.py`, `test_calibrations.py` and `me/test_my_jobs.py` compare whole bodies, lists included, so a `null` field appearing fails them.
3. **CORS:** `Access-Control-Allow-Origin` echoes the request origin on a credentialed request.
4. **Test helpers by job.** Move `insert_if_not_exist`, `get_db_record` and `update_db_record` from `tests/_utils/auth.py` to `tests/_utils/mongodb.py`.
5. **Split `tests/conftest.py`** (527 lines, 34 fixtures). OAuth provider mocks go to `tests/_utils/oauth.py`, the `mock_bcc*` fixtures to `tests/_utils/mock_backend.py`, beside the fake BCC handlers they register (`bcc.py` would make an import cycle with it), the `_to_*_record` converters to `tests/_utils/records.py`; register the fixture modules with `pytest_plugins`. `conftest.py` keeps the environment, stores and client, in that order.
6. **Happy path of every major feature in e2e.** List each feature (login, devices, device detail with bookings and calibrations, projects, tokens, my requests, approvals, notices, settings, admin projects, admin requests, admin control) beside the Cypress spec in `cypress/e2e/` that walks its happy path; add a spec for any that has none. These specs also run against the real stack in `dev/e2e_test.sh`. Job submission has no UI; its happy path stays a pytest flow in `tests/api/rest/test_jobs.py`.
7. **Performance baselines**, recorded before any refactor commit and rerun at every step's sign-off:
   - MSS: a Locust scenario in `dev/perf/locustfile.py` drives the main read and write routes against `dev/perf/docker-compose.yml` (MSS built from the working tree, MongoDB and Redis, seeded from the e2e fixtures). Locust records latency percentiles, throughput, error rate and bytes per request. Alongside it, `docker stats` samples the CPU and memory of every container in the stack, and each database's own status command counts open connections.
   - Dashboard: Lighthouse CI (`@lhci/cli`) on the home, devices, device-detail and projects pages against the mock API, configured in `dev/perf/lighthouserc.json`. It records render timings (LCP, TBT), the JavaScript bundle size and network bytes.
   - `dev/perf/record.sh <dir>` records both; the baselines live in `dev/perf/baselines/`. `dev/perf/compare.py dev/perf/baselines <dir>` exits 1 when a run's p95 latency, failures, peak memory, connections, bundle size or render timing is more than 10% worse than the baseline; such a step is not signed off until the cause is found. The 10% is a starting threshold, to be tuned once the first runs show how noisy each measure is.
8. **`docs/prototypes/`** with a README saying it holds the UAT scripts for this refactor and is deleted at step 10. Delete `docs/rfcs/` and its links in `DESIGN.md`: both RFCs are still marked draft, but the request types and notices they describe are in the code. Confirm nothing in them is still unbuilt before deleting.
9. **Tooling out of the way.** `e2e_test.sh` moves from the repository root to `dev/`. The dashboard's mock API moves from `apps/tergite-dashboard/api/` to `apps/tergite-dashboard/dev/mock-api/`: at the app's root, a folder named `api/` tells a reader the dashboard has a backend of its own. The same commit updates every reference to the old paths: the `test-api` and `dev-api` scripts in `package.json`, the Cypress specs that import the mock's helpers, and the CI workflows that run `e2e_test.sh`.

## Step 2: one shape for every MSS service

Target for each `services/<name>/`: `__init__.py` (re-exports, `__all__` as strings), `dtos.py` (data only), `service.py` (the functions, `on_startup` last), `exc.py` if needed.

1. **Domain errors.** Replace every `HTTPException` raised outside `api/rest/` (`bcc/service.py:777`, `utils/date_time.py:34`, `utils/api.py:226`, `services/auth/*/exc.py`, `services/auth/utils.TooManyListQueryParams`), the `PermissionError` in device events and the `ValueError` in `utils/mongodb.py` with `utils/exc.py` subclasses, mapped in `api/rest/__init__.py`. `ProjectNotExists` and `ProjectExists` stop inheriting fastapi-users' `UserNotExists`.
2. Move `jobs/__init__.py` → `jobs/service.py` and `calibration/__init__.py` → `calibration/service.py`.
3. Move `api/rest/routers/devices/events.py` → `services/devices/events.py`; handlers call `mark_device_online` / `mark_device_offline` instead of building update dicts.
4. **Facades.** Add `__all__` to `devices` and `external/bcc`; add `get_one` and `delete_notice` to `notices`'. Routers import `from services import notices`, never `services.notices.dtos` or `services.requests.service`. `notices/emails.py:20` and `email/service.py:29` stop importing their own facade.
5. **Verbs**, one service per commit: `get_<x>`, `find_<xs>`, `count_<xs>`, `create_<x>`, `update_<x>`, `delete_<x>`.
   - `devices`: `get_all_devices` → `find_devices`; `get_one_device` → `get_device`; `try_connect_device` / `try_disconnect_device` → `mark_device_online` / `mark_device_offline`
   - `calibration`: `get_latest_many` → `find_latest_calibrations`; `insert_one` → `create_calibration`
   - `jobs`: `get_one(is_token_decrypted=)` → `get_job(should_decrypt_token=)`; `remove_job` → `delete_job`
   - `notices`: `toggle_read_status(is_read=)` → `set_read_status`; `toggle_read_status_many(is_read=)` → `set_read_status_many`
6. **Routers resolve, call, wrap.**
   - `routers/jobs.py`: create, cancel and delete orchestration → `jobs.create_job`, `jobs.cancel_job(db, bcc_client, job_id, user_id, request_id, details)`, `jobs.delete_job`. One `bcc.get_client(name)` raising `UnknownBccError` replaces the three inline lookups and `api/rest/utils.get_bcc_client`.
   - `routers/devices/__init__.py:101`: the loop receives and replies; each frame goes through `_handle_frame(data, device, db) -> EventResponse`.
   - `routers/me/requests.py`: keep only the service's role filter (78); delete the not-found check that cannot fire (122).
   - `routers/counts.py:59`: move the superuser override of `user_id` into the service.
7. **`api/rest/dependencies.py`:** every alias `Annotated`, suffixed `Dep`, one name per dependency; delete `CurrentProjectDep`, `CurrentStrictProjectDep` and `CurrentSystemUserProjectDep`, which nothing uses.
8. **A complete OpenAPI schema.** Every route declares its response model, so the schema describes every body; routes that return `.model_dump(...)` dicts are described as empty objects today. `dev/openapi/export.py` writes `app.openapi()` to `dev/openapi/openapi.json` without starting a server (it works although production serves no docs); the file is committed, and CI fails when it is stale. The dashboard generates its client from it in step 9.1.
9. **Split `utils/api.py`.** Error handlers → `api/rest/errors.py` as `make_http_error_handler` and `make_exception_group_handler`; `verify_ws_signature` and `_get_bcc_public_key` → `utils/crypto.py`; response shapes stay. `PaginatedListResponse.model_dump(exclude_data_none_fields=)` becomes `build_paginated_json(data, skip, limit, should_exclude_none=True)`, used by every list route.
10. **Delete dead code:** `date_time.is_in_month`, `to_datetime`, `parse_datetime_string`; `logging.log_if_err`, `err_logger`; `models.try_parse_record`; `TooManyRequestsError`, `InvalidWebsocketDataTypeError`; `calibration.get_historical_many`; `NoticeTemplatePartial`, `CustomNoticeCreatePartial`; `settings.root_logger`, `PRIVATE_KEY_PASSWORD`; `utils/api.get_bearer_token`.
11. **Delete unused dependencies.** `requests` is imported nowhere. `tomli` is used only by `tests/_utils/env.py`, which can use the standard library's `tomllib`. `aiohttp` is used only by `tests/_utils/aiohttp.py`, which can use `httpx`, already a dependency.
12. **Settings come in as arguments** (convention 7), one service per commit. Remove every default argument bound to a global (`settings.CONFIG` in `jobs.update_qpu_usage`, `notices.create_system_notice`, `Emailer.__init__`, `datetime_to_zulu` and every `BccClient` method; `PRIVATE_KEY_FILE` and `settings.CONFIG.private_key_password` in `jobs.get_job`). Then remove every other read of `settings` outside `api/rest`: today in `services/auth/service.py`, `auth/users/__init__.py`, `auth/projects/__init__.py`, `auth/providers/__init__.py`, `auth/app_tokens/authenticator.py` and `utils/api.py`. Each value is passed explicitly where the function is called. A module whose functions are called from many places, or from `default_factory` fields, is instead given the value once by the lifespan, through its `on_startup` or a setter, and keeps it module-private (convention 7's exception), so that callers do not carry another service's settings.
13. Delete the section-label comments (`# Derived models`, `# exception handlers` and the like) in `api/rest/__init__.py`, `app_kwargs.py`, `settings.py`, `jobs/dtos.py`, `devices/dtos.py`, `calibration/dtos.py`. The Apache 2.0 licence header at the top of each file is not a banner; it stays, and every new file gets it.

## Step 3: storage layer, MongoDB first

Services stop touching MongoDB. They read and write through one `Database` object, and the code outside `libs/storage` never learns which database technology sits behind it. This step ships only the MongoDB backend, so no behaviour changes; step 4 adds SQL.

No reputable library offers one query interface over both MongoDB and SQL, so the abstract layer is ours, kept to the operations MSS actually uses. Each backend leans on its database's own library: PyMongo's async API for MongoDB (Motor, used today, was deprecated on 14 May 2026 in its favour) and SQLAlchemy for SQL. Where databases differ, the backend absorbs the difference.

**The design.** `Database` is created with a `database_url` and the schemas it holds. It keeps a private `__db_store`, a `DbStore`: the abstract class that `MongoStore` and `SqlStore` implement, picked from the scheme of `database_url`. A method that works on one schema takes that schema first and returns instances of it. Passing a schema the `Database` was not created with raises `UnknownSchemaError`. A method that spans schemas takes none; MSS needs none today. One `Database` exists per process: the lifespan builds it, and FastAPI's dependency injection hands it to whatever needs it. So `database` replaces `db` as the first argument of every service function.

"Repository" usually names one object per entity type (as in domain-driven design and Spring Data). This object fronts the whole database, so it is called `Database`, and calls read plainly: `database.find(Job, filter={"status": "pending"})`.

**Schemas.** Every stored schema subclasses `Schema`, the storage layer's Pydantic base, and declares its storage facts in a `__storage__` class attribute that names no technology: its table, its key, which fields are unique, case-insensitive or expiring, `references` (a map from a field to the schema whose keys it holds; a scalar field becomes a foreign key, a list field a join table) and `indexed_lists` (other list fields whose elements are queried or written one at a time). Each `DbStore` turns those facts into its own indexes and tables. The facts live on the schema in its service's `dtos.py`, so there is no separate persistence file to keep in step.

**No technology-specific classes, so nothing to proxy.** Beanie leaves in this step, `MongoStore` talks to PyMongo with plain dicts, and `SqlStore` builds SQLAlchemy Core tables privately (step 4). Each store validates what it reads into the caller's `Schema` subclass and returns that instance. A wrapper that generated Beanie `Document`s or ORM classes and proxied results back would be a second model hierarchy to keep in step with the first, which is exactly the fight with the libraries this plan avoids.

**Ids name no technology either.** `Id` is a string of 24 lowercase hex characters, time-ordered, generated by `generate_id()`, the same shape as today's ids. `MongoStore` stores it as an `ObjectId`, so existing documents, indexes and references stay as they are; `SqlStore` stores it as a 24-character string. Nothing above the storage layer sees `ObjectId` or `PydanticObjectId`.

The layer is part of MSS, under `libs/` beside `authlib` (step 6). Code in `libs/` imports nothing from `api/`, `services/` or `settings`, so dependencies run one way: `api → services → libs`.

```
apps/tergite-mss/
├── libs/
│   ├── __init__.py
│   ├── storage/
│   │   ├── __init__.py       re-exports Database, Schema, StorageSpec, Id, Filter, Update and Returning
│   │   ├── database.py       Database: picks the DbStore by URL scheme, rejects schemas it was not given
│   │   ├── base/             the abstract layer every backend implements
│   │   │   ├── store.py          DbStore, the abstract class
│   │   │   ├── schema.py         Schema, StorageSpec
│   │   │   ├── ids.py            Id, generate_id(), derive_id()
│   │   │   ├── query.py          Filter and its checks: MongoDB's query operators, sort strings
│   │   │   └── update.py         Update and its checks: MongoDB's update operators, Returning
│   │   ├── mongo/            MongoStore on pymongo.AsyncMongoClient; translate_filter(), translate_update()
│   │   └── sql/              SqlStore, step 4
│   └── authlib/              step 6
├── api/rest/database.py      builds the Database in the lifespan; DatabaseDep
└── tests/libs/storage/       unit and conformance tests
```

```python
class Project(Schema):
    __storage__ = StorageSpec(table="projects", key="id", unique=("name",), references={"admin_id": User, "user_ids": User})

    id: Id = Field(default_factory=generate_id)
    name: str
    admin_id: Id
    user_ids: List[Id] = []
    qpu_seconds: float = 0


class Database:
    def __init__(self, database_url: str, schemas: Sequence[type[Schema]]):
        self.database_url = database_url
        self.__schemas = frozenset(schemas)
        self.__db_store = _create_store(database_url, schemas)

    async def get(self, schema: type[T], key: Id) -> Optional[T]:
        return await self.__db_store.get(self.__ensure_registered(schema), key)

    async def find(self, schema: type[T], filter: Optional[Filter] = None, sort: Sequence[str] = (), skip: int = 0, limit: Optional[int] = None) -> List[T]: ...
    async def count(self, schema: type[T], filter: Optional[Filter] = None) -> int: ...
    async def insert(self, schema: type[T], record: T) -> T: ...
    async def update_one(self, schema: type[T], filter: Filter, update: Update, *, should_upsert: bool = False, returning: Returning = Returning.AFTER) -> Optional[T]: ...
    async def update_many(self, schema: type[T], filter: Filter, update: Update) -> int: ...
    async def delete_many(self, schema: type[T], filter: Filter) -> int: ...
    async def close(self) -> None: ...

    def __ensure_registered(self, schema: type[T]) -> type[T]:
        if schema not in self.__schemas:
            raise UnknownSchemaError(schema)
        return schema
```

Beside those, `Database` has the other operations MSS uses today: `setup()`, which the lifespan calls to create indexes and tables, `find_one`, `find_distinct`, `insert_many` and `delete_one`. `StorageSpec.indexes` declares the plain and compound indexes the queries rely on (a leading `-` marks a descending field), so that none of today's indexes is lost.

**Filters and updates are MongoDB's own dialect**, kept to what every store can translate: `filter={"id": pk, "user_id": {"$in": [user_id, None]}}` with `$eq`, `$ne`, `$in`, `$nin`, `$gt`, `$gte`, `$lt`, `$lte`, `$and` and `$or`; `update={"$set": {…}, "$inc": {…}}` with `$set`, `$setOnInsert`, `$inc`, `$addToSet` and `$pull`; `sort=["-created_at"]`, `skip`, `limit`. A dict is parsed data, so no store parses text: `MongoStore` passes it through with its ids converted, and `SqlStore` (step 4) checks each field against the schema and binds every value as a parameter, so a caller's input never reaches SQL text. `Database` refuses an unknown operator or field before any store sees it. Fields are dotted for nested objects (`timestamps.execution.started`). Service functions take their query's arguments, or its query model, and build the filter privately; routes never build one.

`Database` checks every `__storage__` against its schema when it is created (field names exist, referenced schemas are registered too), so a mistake fails at boot, not on a request.

**One async interface, no sync twin.** Every caller is async: the routes, the websocket handler, the lifespan and the email sweeper. Alembic connects on its own. Sync tests seed and inspect through `tests/_utils/storage.py`, which wraps each call in `asyncio.run` with a short-lived `Database`. A sync twin would double every backend and its conformance tests; a sync caller that appears later uses `asyncio.run` the same way.

1. **`libs/storage/base` and `Database`.** `Schema`, `StorageSpec`, `Id`, the query and update structs, the abstract `DbStore`, and `Database` with its schema checks, unit-tested in `tests/libs/storage/` against an in-test `DbStore` double. The function `derive_id(parent_id, namespace)` replaces `utils/crypto.generate_linked_id`: it computes an id deterministically from another, as a user's personal project id is computed from the user's id today (`services/auth/projects/database.py:51`). It must compute exactly the ids the old function did, so existing personal projects are still found; a test pins a few known pairs.
2. **`MongoStore`** for `mongodb://` and `mongodb+srv://`, on `pymongo.AsyncMongoClient`, with pure `translate_filter` / `translate_update` tested table-first, no database. It converts `Id` to and from `ObjectId` at its edge. Indexes come from each `__storage__`: unique, case-insensitive collation, TTL on the expiring field, multikey on list `references` and `indexed_lists`. The `$jsonSchema` validator moves here from `utils/mongodb.py`. A conformance test runs every `Database` method against a real MongoDB.
3. **Wiring.** `database.url` accepts every supported scheme instead of only `MongoDsn`. `api/rest/database.py` builds the `Database` in the lifespan from every service's schemas, keeps it on `app.state`, and closes it on shutdown; `DatabaseDep` replaces `MongoDbDep`. It is one instance by construction, not a module global (convention 7).
4. **The request log becomes a schema, kept in a cache.** It remembers request ids and websocket nonces long enough to reject a replay: a `RequestLog` schema keyed by `request_id`, with the expiring field. `services/request_log/service.py` holds `record_request(database, request_id, ttl) -> bool`, an `insert` where a duplicate key means "already seen", and `is_request_recorded(database, request_id)`. It is written on every request, so it lives in Redis, behind a `Database` of its own on `database.redis_url` that the lifespan opens beside the main one; the middleware (`api/rest/middleware.py:66`) and the nonce check (`api/rest/utils.py:108`) get that `Database`. Its `RedisStore` is `utils/redis_store.py` adapted to the `DbStore` (step 4's last paragraph), and `tests/test_store.py` is ported with it. A first version kept the request log in MongoDB and dropped Redis; it doubled p95 latency under load (the step 3 UAT).
5. **Move services onto the `Database`**, one service per commit: `jobs`, `devices`, `calibration`, `notices`, `requests`. Their stored DTOs become `Schema` subclasses with a `__storage__`. Services take `database` first (`jobs.get_job(database, job_id)` calls `database.get(Job, job_id)`); service functions take the query models, whose set fields are the filter. Four spots need a translation, not a rename:
   - `notices/service.py:151-172` and `621-627` update each notice differently by type with an aggregation pipeline (`$cond`, `$setUnion`). Each becomes two plain updates: one filtered to broadcast notices (`$addToSet` / `$pull` on `dismissed_by`), one to the rest (`$set` on `read_at`).
   - `jobs/service.py:180` reads the job as it was before the update, to detect the first usage report: `update_one(Job, …, returning=Returning.BEFORE)`.
   - `devices/service.py:91` and `calibration/service.py:62` upsert: `update_one(…, should_upsert=True)` with `SetOnInsert`.
   - `auth/service.py:155` searches emails with a case-insensitive `$regex`. It stays on the Beanie `User` until step 7, which adds the substring operator it needs to the dialect, with its SQL translation.
6. **`Id` replaces `PydanticObjectId`** everywhere above the storage layer: 163 uses in 29 files across `api/rest`, `services` and `utils`, one package per commit. Path parameters typed `Id` keep answering 404 for a malformed id (the step 1.1 contract). The ids of the Beanie `User` stay `PydanticObjectId` until it moves in step 7, so the BCC client keeps taking user ids as `str | PydanticObjectId`, and code reaching the Beanie `User` or the auth documents converts at that boundary.
7. **Delete `utils/mongodb.py`, Motor and Beanie** for every schema except `User`, which moves in step 7. The eight `Document` classes become `Schema` subclasses; their index declarations become their `__storage__`.

## Step 4: SQL adapter on normalised tables

Only a new `DbStore`, so no service changes. One rule decides the tables: **a field gets its own table if its elements are queried, or written one at a time, apart from the parent.** A field always read and written whole with its parent is a column on the parent, using SQLAlchemy's generic `JSON` type when nested, and validated by its Pydantic model on every read and write. These fields are never queried, so a database-specific type such as PostgreSQL's `JSONB` would buy nothing.

**Generic SQLAlchemy first.** `SqlStore` is written against SQLAlchemy's generic API, so `Database` accepts any SQLAlchemy URL with an async driver and nothing in our code names a database. Where a database lacks a construct, `SqlStore`'s generic path covers it inside a transaction, as listed in item 3. A database-specific construct is used only where it is needed for correctness or saves a measurable amount, and only behind a capability flag SQLAlchemy already exposes. Callers never see which path ran. CI's conformance tests run PostgreSQL (`postgresql+asyncpg://`) and SQLite (`sqlite+aiosqlite://`); another database is supported once it joins that matrix.

**Tables come from the schemas.** When the `Database` is created, `SqlStore` builds SQLAlchemy Core `Table`s from each schema's fields and `__storage__`: a column per scalar field, a `JSON` column per nested field, a foreign key per scalar `references` entry, a join table per list `references` entry, and a child table per `indexed_lists` entry. Services write no SQL and no ORM classes, and the same `__storage__` drives MongoDB's indexes. Rows become schemas through `model_validate(..., from_attributes=True)`. Not SQLModel: it covers SQL only and would turn our schemas into table classes the MongoDB backend cannot use.

1. **`SqlStore`** and its table derivation, with `translate_filter` and `translate_update` pure and unit-tested against sample schemas.
2. **One schema at a time**, one commit each, each passing the conformance test on PostgreSQL and SQLite. The table shows what `SqlStore` derives; the last column is why a schema's `__storage__` lists a field in `references` or `indexed_lists`.

| Schemas | Tables | JSON columns | Why a child table |
| --- | --- | --- | --- |
| projects, deleted projects | `projects`, `project_users`; `deleted_projects`, `deleted_project_users` | — | projects are found by member (`projects/routers/__init__.py:84`); members are added and removed one at a time |
| users (step 6) | `users`, `roles`, `user_roles`, `oauth_accounts` | — | admins are found by role (`requests/service.py:280`); roles are granted one at a time when an account is linked; sign-in looks an account up by provider and account id (`indexed_lists`). `Role` is a schema keyed by its name and seeded from `UserRole` |
| app tokens | `app_tokens` | — | — |
| jobs | `jobs` | `timestamps`, `result` | — |
| devices | `devices` | `basis_gates`, `coupling_map`, `coordinates`, `coupling_dict`, `meas_map`, `qubit_ids`, `meas_lo_freq`, `qubit_lo_freq`, `gates`, `qubit_ids_coupler_map` | — |
| calibrations, calibration logs | `calibrations`, `calibration_logs` | `qubits`, `resonators`, `couplers`, `discriminators` | — |
| notices | `notices`, `notice_users` (dismissals) | `context` | notices are filtered by who dismissed them (`notices/service.py:528-554`); each dismissal is one write |
| notice preferences | `notice_preferences` | `email_prefs` | kept as one map per user in step 4: a row per type would change the shape MongoDB holds too, which needs a data migration. Until then two concurrent `set_email_preferences` calls can lose one change, as on MongoDB |
| notice templates | `notice_templates` | — | — |
| user requests | `requests`, `request_users` (targets) | `metadata` | requests are found by target (`requests/service.py:109, 147, 204`) |
| request logs | `request_logs` | — | — |

Every JSON field is written whole: devices are upserted whole on `initialized`, calibrations inserted whole, job `timestamps` and `result` set whole by `update_job`, notice `context` and request `metadata` written once at creation. `DeviceQuery` and `DeviceCalibrationQuery` already exclude the device and calibration ones from filtering.

Names follow the usual SQL convention: plural snake_case tables, foreign keys named `<singular>_id`, and many-to-many tables named after the two tables they join, singular first (`project_users`). A new query on a JSON field, or a write to part of one, is the signal to move it to its own table, in the commit that adds it.

3. **How each operation runs on SQL**, generic first, each covered by the conformance test on every database in the matrix:
   - list membership (`user_ids` contains X) → an `exists()` subquery on the child table
   - a filter → a SQLAlchemy Core `where` clause built from the dict: each field resolved against the schema to a column, each value a bound parameter, `$and`/`$or` → `and_()`/`or_()`
   - `$addToSet` → insert the child row inside a savepoint; a unique-key conflict on the pair means it was already there. `$pull` → delete the child row
   - `$inc` → `column = column + n`
   - `should_upsert` → `UPDATE`, then `INSERT` if no row matched, retrying the `UPDATE` on a unique-key conflict, all in one transaction
   - `returning=BEFORE` → `SELECT … with_for_update()`, then `UPDATE`, in one transaction. `returning=AFTER` → `UPDATE`, then `SELECT`; where `dialect.update_returning` is true, a single `UPDATE … RETURNING` instead. SQLAlchemy drops `FOR UPDATE` where a database has no row locks, and on SQLite `SqlStore` begins write transactions immediately, so the read already holds the write lock
   - a write to a record and its child tables runs in one transaction
   - case-insensitive unique email → a unique index on `func.lower(email)`, and equality on it compares `func.lower` of both sides
   - expiring records (`notices`, `request_logs`) → every read filters on `expires_at`, and the lifespan runs a periodic delete, since SQL has no TTL index
4. **Migrations.** Alembic in `apps/tergite-mss/migrations/`, autogenerated from the `MetaData` that `SqlStore` builds and reviewed by hand; `start_mss.sh` runs `alembic upgrade head` when the URL is SQL.
5. **Test matrix.** The `db` fixture is parametrised over `TEST_DATABASE_URLS` (MongoDB, PostgreSQL, SQLite). Tests seed and inspect through a `Database` in `tests/_utils/storage.py` instead of raw pymongo in `tests/_utils/mongodb.py`. CI adds a PostgreSQL job beside the MongoDB one.
6. **Docs.** `mss-config.example.toml` lists the accepted URL schemes; the Data section of `DESIGN.md` is rewritten.

**`RedisStore` serves caches, not records.** It is the store the request log used before step 3, adapted to the `DbStore`: a hash per table, per-field expiry, and a sorted set per indexed value. It answers equality and `$in` on indexed fields and `$set` updates, and refuses the rest with `QueryError`, so it holds what is read by key on every request (the request log), behind its own `Database`, while records stay in MongoDB or SQL.

Moving an existing deployment's data from MongoDB to SQL needs an export/import script. It is not in this plan.

## Step 5: MSS auth, projects and app tokens

`projects/` and `app_tokens/` are 2,355 of `services/auth`'s 3,725 lines. fastapi-users has no projects or app tokens; this code copies its manager, database, strategy, backend and authenticator structure for features it never offered. It becomes plain functions that take the `Database` first, independent of `authlib`. Every commit keeps the step 1.1 contract.

1. **`projects/service.py`** absorbs `ProjectDatabase`, `ProjectAppTokenManager`, `projects/routers/handlers.py` and `projects/routers/utils.py` as `get_project`, `get_project_if_member`, `find_projects`, `create_project`, `update_project`, `remove_member`, `delete_project`, `ensure_personal_project`, `increment_qpu_seconds`, `get_admin_view`. `notify_membership_change` and the email/id maps go to `projects/membership.py`. `requests/actions.py` calls these and loses `_get_project_manager`, which hand-builds a manager from three "databases". `get_project_db`, `get_app_token_db` and the `ProjectDatabase` and `AppTokenDatabase` that `projects.on_startup` holds since step 3.7 go with them, as every caller then passes the `Database`.
2. **`app_tokens/service.py`** absorbs `AppTokenDatabase`, `AppTokenStrategy` and `AppTokenAuthenticationBackend` as `create_app_token`, `get_token_owner`, `find_app_tokens`, `update_app_token_expiry`, `delete_app_token`, `delete_project_tokens`, `delete_non_member_tokens`.
3. **`services/auth/access.py`** plus `get_current_project`, `get_current_lax_project`, `get_current_system_project` and `get_current_project_user_ids` in `api/rest/auth.py`. Delete `AppTokenAuthenticator`, `ProjectBasedAuth`, `AuthMetadata`, the `GET_CURRENT_*PROJECT*` constants and their `makefun` signatures. Add `tests/services/auth/test_access.py`: a parametrised table, no `db` fixture.

```python
STRICT = AccessRule(is_qpu_required=True)
LAX = AccessRule(is_qpu_required=False)
SYSTEM = AccessRule(is_qpu_required=True, roles=(UserRole.SYSTEM,))


def check_project_access(owner: Optional[TokenOwner], rule: AccessRule) -> Project:
    if owner is None or not owner.project.is_active:
        raise UnauthorizedError()
    if rule.is_qpu_required and owner.project.qpu_seconds <= 0:
        raise ForbiddenError(f"{owner.project.qpu_seconds} QPU seconds left on project {owner.project.name}")
    if rule.roles and not owner.user.roles & set(rule.roles):
        raise ForbiddenError()
    return owner.project
```

4. **`notices.create_system_notice` and `clear_notices_by_reference` take the `Database`** as their first argument, now that their callers in `auth` have one; step 3.5 gave them the one `notices.on_startup` holds, as those callers had none to pass.
5. **Routes out of the service.** `projects/routers/__init__.py` and `app_tokens/routers.py` become `api/rest/routers/me/projects.py`, `me/tokens.py` and `admin/projects.py`. `ProjectQuery` and `AppTokenQuery` models, injected with `Depends()`, replace the hand-listed `Query(...)` parameters and are passed to the service functions, which build their filters privately. Path parameters are typed `Id` (step 3.6).

## Step 6: `libs/authlib`, a stripped copy of fastapi-users

Copy fastapi-users 14.0.2 (2,926 lines, MIT-licensed, in maintenance mode upstream) into `libs/authlib/`, and its test suite into `tests/libs/authlib/`. No fork and no separate repository: from the day it lands it is MSS code. It keeps the battle-tested user and session code and its tests, drops what tergite never calls, absorbs what MSS bolts on today, and persists users through `libs/storage`. JWTs stay on PyJWT and provider clients on httpx-oauth, as upstream has them.

1. **Baseline.** Copy source and tests unchanged except the import path. Keep upstream's licence as `libs/authlib/LICENSE` and credit fastapi-users in `CREDITS.md`; MIT requires the notice to stay. Each copied file gets the tergite Apache 2.0 header, with a line naming fastapi-users and its MIT licence, as the header already names other contributing parties. Its dependencies stay until the code that needs them goes. The copied suite passes before anything else changes.
2. **Strip**, one feature per commit, deleting its tests in the same commit, suite green after each:
   - `router/register.py`, `router/reset.py`, `router/verify.py`, `router/users.py` and their manager methods (create with password, authenticate, forgot/reset password, request/verify)
   - password login in `router/auth.py`, keeping logout; `password.py`
   - `authentication/strategy/db/` and `authentication/strategy/redis.py`; the JWT strategy stays
   - `db/base.py` (`BaseUserDatabase`), replaced in item 3
3. **Users on storage.** `authlib` reads and writes users through the `Database` it is given, so it never learns the technology. `User` and `Role` are `Schema` subclasses in `services/auth/users/dtos.py`, from which `SqlStore` derives `users`, `roles`, `user_roles` and `oauth_accounts` (step 4); `User` keeps today's `auth_users` documents field for field. The `authlib` tests run on SQLite and MongoDB.
4. **Absorb what MSS bolts on**, one commit each, with tests:
   - a `roles` claim in the session JWT (today `CustomJWTStrategy`)
   - a current-user-id dependency that skips the database (today `UserAuthenticator.current_user_id`)
   - a roles requirement on the current-user dependency (today `UserAuthenticator.current_user(roles=)`)
   - per-provider `email_regex`, checked before sign-in, and per-provider `roles`, added when an account is linked or created (today `EmailRegexValidator` and `UserDatabase.add_oauth_account`)
   - a JSON logout body, `{"message": "logged out"}` (today `JwtCookieTransport`)
   - an `on_after_login` callback argument (MSS uses it for the personal project; today a `UserManager` override with a function-local import)
5. **One parametrised OAuth router**: `/{provider}/authorize`, `/{provider}/auto-authorize`, `/{provider}/callback`, with an option for the `/app/{provider}` alias. It replaces one router per client and the copy of upstream's OAuth router in `services/auth/users/routers.py`. Credentials are read with FastAPI's `HTTPBearer` and `APIKeyCookie`, which removes the `makefun` signatures.
6. **Reshape to the conventions.** Stateless pieces become functions: JWT and state-token encode/decode, and the account-linking rule. The configured auth object, which holds providers, secrets and the `Database`, stays a class.
7. **Pin the invariants in tests:** the account-linking rule (match by provider account; else by email, linking only if `associate_by_email`, otherwise 400 `OAUTH_USER_ALREADY_EXISTS`; else create), the session audience `fastapi-users:auth` and the state audience `fastapi-users:oauth-state`. Live cookies and the dashboard mock API depend on both audiences.

## Step 7: MSS switches to `authlib`

Every commit keeps the step 1.1 contract; `dev/e2e_test.sh` runs after the last one.

1. **Switch the imports.** `api/rest/routers/auth.py` mounts `authlib`'s OAuth router for the configured providers; the user dependencies in `api/rest/auth.py` come from `authlib`; the personal-project rule is passed in as `on_after_login`. fastapi-users and fastapi-users-db-beanie leave `pyproject.toml` and the lock.
2. **Delete the subclasses** `authlib` made unnecessary: `UserBasedAuth`, `UserAuthenticator`, `CustomJWTStrategy`, `JwtCookieTransport`, `UserManager`, `UserDatabase`, `Validator`, `EmailRegexValidator`, `users/routers.py`, `service.register_oauth2_client`, `_AUTH_EMAIL_REGEX_MAP`, `_AUTH_ROLES_MAP`, the `UP` / `ID` type variables and the `Current*Dependency` aliases.
3. **Users on storage.** `auth_users` leaves Beanie, which leaves `pyproject.toml`; `User.hashed_password` becomes optional, so existing documents still load. `get_user_emails` searches emails as a case-insensitive substring, which needs the one operator the dialect adds here: MongoDB's `$regex` limited to escaped text with `$options: "i"`, which `SqlStore` translates to `ilike` with the pattern escaped. `tests/_utils/auth.py` drops `PasswordHelper`. One `Changed` changelog entry.

## Step 8: MSS classes and long functions

1. **`BccClient` stays a class**: it owns an `httpx.AsyncClient` per backend. Trim it: the lifespan builds each client with the MSS private key already loaded, so `_create_headers` signs with `self`'s key and 15 methods lose `private_key_file` and `key_password`; drop the unused `files`, `timeout` and `**kwargs` parameters, the unused `base_url` attribute and the copied httpx type hints (687-724). `_request` is split in item 7.
2. **`Emailer` stays a class**: it owns the sweeper's background tasks. Trim it to the one schedule it runs: delete the multi-schedule map and the unused `get_schedule` and `send`; `EmailDetails.to_email_message` becomes its private `_get_email_message(details)`. Start it from the lifespan in `app_kwargs.py`, not from `notices.on_startup`.
3. **`WebsocketConnectionManager` stays a class**: it owns the live device sockets. Move it from `utils/api.py` to `routers/devices`, its only user; delete `broadcast` (unused) and `reply` (it only forwards to `send_json`).
4. **Middleware stays as Starlette subclasses.** `TergiteCORSMiddleware` goes only if stock `CORSMiddleware(allow_origin_regex=".*", allow_credentials=True, …)` passes the step 1.3 test. `EndpointFilter` holds no state, so it becomes a filter function.
5. **`NoticeType(NoticeTypeInfo, Enum)`** → `NoticeTypeId(StrEnum)` plus a `NOTICE_TYPE_INFO: dict[NoticeTypeId, NoticeTypeInfo]` constant. Delete `from_str`, `__str_member_map__`, the `Literal[tuple(…)]` hack and `utils/types.py`. `DeviceEventHandler(Protocol)` → a `Callable` alias.
6. **Behaviour off DTOs**, one service per commit; class-level dunder maps become module constants.
   - `notices`: `CustomNoticeCreate.to_documents` (does I/O) → `_get_custom_notices(db, payload, created_by)`; `Notice.from_template` → `_render_notice`; `NoticeSeverity.to_int` → `_SEVERITY_RANK`
   - `requests`: `Request.notice_type`, `notice_context`, `from_post_body`, `RequestPostBody.target` and the three `__type_*_map__` → `requests/service.py`
   - `devices`: `DeviceEvent.__status_data_map__` → a constant in `events.py`
   - `utils/config.py`: `BccConfig.ip_address` (a DNS lookup in a `computed_field`) → `get_ip_addr(conf.url.host)` at `api/rest/utils.py:87`
   - `jobs`: `JobStatusResponse.from_job` → inline
7. **Long functions become compositions**, one per commit, with unit tests for the pure steps.

| Function | Lines | Composed of |
| --- | --- | --- |
| `bcc` `_request` | 104 | `_send`, `_raise_for_bcc_error(response)` |
| `requests.update` | 94 | `_find_pending_for_approver`, `_record_decision`, `_clear_approver_notices`, `_notify_requesters` |
| `notices.create_system_notice` | 66 | pure `_get_email_status_map(user_ids, preferences, is_email_enabled)`, `_render_notices` |
| `jobs.update_qpu_usage` | 65 | pure `_choose_qpu_notice(before, after, threshold)`, `_notify_project` |
| `email._send_on_repeat` | 64 | `_send_batch(smtp, batch, sender, should_ignore_errors)` |
| `notices.find_many` | 60 | a `NoticeFilter` model shared with `count_many` and `set_read_status_many` |
| `storage.mongo._to_mongo_json_schema`, renamed `_convert_to_mongo_json_schema` | 57 | `_resolve_ref`, `_map_to_bson_type`, `_keep_mongo_keywords` |
| `api/rest/utils.get_verified_device_name` | 56 | `_read_signed_headers`, `_check_client_ip`, pure `_check_nonce_age(timestamp, now, ttl)`, `_check_nonce_unused` |
| `logging.setup_logging` | 56 | `get_log_level(env)` (shared with `settings.py`), `_add_sink`, `_route_std_logging` |
| `notices/emails.process_email_batch_results` | 54 | pure `_partition_results`, `_record_attempts(ids, status)` |
| `notices.clear_notices_by_reference` | 53 | pure `_get_ref_filter(refs, now)`, `_get_cleared_update(timestamp, now)` |

8. **Flatten DTO inheritance** by spelling fields out, JSON unchanged: `DeviceCalibrationLog` (three levels), `Request(RequestPostBody, Document)`, `CreateProjectMetadata(RequestMetadata, ProjectCreate)`.
9. **Last:** remove the four remaining `model_dump` overrides (`utils/api.py:62`, `utils/models.py:43`, `jobs/dtos.py:159`, `devices/dtos.py:94`) and pass the flags at the call sites. The step 1.2 body tests catch a missed call site.

## Step 9: dashboard

The co-located page hierarchy, the `index / columns / filter-form` table split and loaders beside their pages stay. The two largest hand-written pieces, the API client and the response types mirrored from MSS, become generated code.

1. **Generate the API contract.** `openapi-typescript` generates `src/lib/api/schema.d.ts` from `dev/openapi/openapi.json` (step 2.8) with `npm run generate:api`; CI fails when it is stale. An `openapi-fetch` client in `src/lib/api/client.ts` (base URL, `credentials: "include"`, one error middleware) replaces `authenticatedFetch`, `getQueryString` and `extractError`; it is the only file that talks HTTP. A change to an MSS DTO now fails `tsc` in the dashboard instead of a Cypress run.
2. **Split `src/lib/api-client.ts`** (1,836 lines) into one module per resource under `src/lib/api/` (`devices`, `bookings`, `projects`, `tokens`, `requests`, `notices`, `admin-control`, `auth`), each holding react-query options and mutations that call the typed client in one line. In the same commit:
   - the `baseUrl` option on about 50 functions goes; the client holds the base URL
   - the dozen single-use private getters fold into their `queryFn`; `getFutureBookings` folds into `upcomingBookingsQuery`
   - delete `calibrationsQuery`, `removeProjectMember`, `refetchInterval`; un-export `getNotices`, `getNoticeCount`, `getRecalibrationInfo`
   - the eight `refresh*Queries` become one-liners
   - `myTokensQuery` stops joining projects inside `queryFn` (its `projectList` is not in the key); the page joins with a pure `addProjectNames(tokens, projects)`
3. **Empty `src/lib/utils.ts` down to `cn`.** `getCalibrationMedians` → `device-summary.tsx`; unit converters and `extend*` → the api module that uses them; `loadOrRedirectIfAuthErr`, `tryQueryFetchMany` → `lib/loaders.ts`; `getUserRequestTitle`, `getUserRequestDetails` → `lib/user-requests.ts`; `SEVERITY_LABELS` → `ui/notice-banner.tsx`. Time helpers go to `lib/time.ts`; each one kept there must do more than a single Luxon call, or it is replaced by that call.
4. **Router built once.** App state moves to a `zustand` store with its `persist` middleware: `currentProjectId`, `apiToken` and the dark-mode flag, which replaces `getSavedIsDarkMode` / `saveIsDarkMode`. Loaders read `useAppStore.getState()`; components use the hook. `router.tsx` exports a module-level route array passed once to `createBrowserRouter`. One `ErrorBoundary` around `<Outlet/>` in the dashboard layout and one around the login page replace `ErrorBound` and its 12 wraps.
5. **Loaders.** `queryClient.ensureQueryData(query)` replaces the 11 hand-rolled `getQueryData(…) ?? await fetchQuery(…)`. Loaders return data, not query options (`tokens/index.tsx:118`, `home/index.tsx:132`). The home loader uses `Promise.all`. `device-detail` reads the device and calibration through `useQuery`.
6. **Mutations invalidate in their own `onSuccess`**, not through parent callbacks (`admin-projects/index.tsx:63-83`).
7. **Components**, one page folder per commit:
   - delete the six `*Sidebar` wrappers that choose summary or placeholder by casting props; the page chooses
   - `QpuTimeDialog` + `_QpuTimeDialog` → `QpuTimeRequestDialog`; the `N/A` branch moves to `columns.tsx`
   - `bookings-calendar/index.tsx` (490 lines): `BookingEventContent` → `event-content.tsx`; pure `isBookingEditable(booking, userId, isAdmin)` replaces the copies at 190 and 384; static calendar options → a module constant; `getEventClassNamesGenerator` → `getEventClassNames`
   - `calibration-map-chart.tsx`: ten `useMemo`s → pure `computeQubitLayout(device, calibration, prop, size)`; `buildCalibrationPoints(calibration, prop)` shared with the bar chart
   - `admin-projects`: the six project fields written twice → `project-fields.tsx`
   - request-detail rendering, copied three times → `components/ui/request-details.tsx`
   - sidebar and mobile menu render one `NAV_GROUPS` array from `nav-items.ts`
   - delete memo hooks that cannot hit, e.g. `booking-form.tsx:82-113`
8. **Delete `types.ts`.** Response and request types come from `schema.d.ts`; the client-only shapes (`Time`, `InputDuration`, `CalibrationDataPoint`, `AppState`) move next to their users in `src/`.
9. **Names.** `isFormDirty` (a number) → a boolean; `use` → `forwardAsyncErrors`; `NotFound` → `createNotFoundError`; `handleEventDrop` → `bookingMove`; `sortBookings` → `pickEarliestBookings`; `chatData` → `chartData`; `meta.ts` → `notice-type-styles.ts`; `isUserAdmin` → `isAdmin`.
10. **Split the mock API** (`dev/mock-api/routes/general.ts` 1,825 lines, `dev/mock-api/utils.ts` 880) into `db.ts`, `auth.ts` (no db import), `http.ts`, `notices.ts`, `requests.ts` and `routes/{me,devices,bookings,admin-projects,bcc,notices,requests}.ts`. Its handlers are typed against `schema.d.ts`, so the mock cannot drift from MSS unnoticed. `requireUser` and `requireRole(UserRole.ADMIN)` Express middleware replace 46 copies of the auth preamble and 19 role checks. `MockDb` keeps its rows as data, with `createFreshDb()` replacing the initial state written twice.
11. **Cypress.** `cy.loginAs(user)` and `cy.resetDb()` replace the block repeated in 14 specs; specs import `dev/mock-api/auth.ts`, not `dev/mock-api/utils.ts`; `cypress/support/utils.ts` imports `extendAppToken` and `getUserRequestDetails` from `src/` instead of copying them.

## Step 10: close out

1. Read `DESIGN.md` and both app design docs against the tree. Every path they name exists, and every package has the shape they describe. Today they still name `services/notifications`, `outbox.py` and `request_logging_middleware`, and say there is no code generation from the OpenAPI schema.
2. Run `dev/e2e_test.sh` and the step 1.7 performance checks once more against the merged result.
3. Delete `docs/prototypes/` and this file; the history keeps both.
