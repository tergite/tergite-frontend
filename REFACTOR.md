# Refactor plan

Steps 0 to 7 are done; steps 8 to 10 remain, below. Each numbered item is one commit, verified before the next. Step 9 (the dashboard) can run in parallel with step 8.

## Conventions

The code reads like an article: the overview first, the detail below it. Every step applies these rules to the code it touches, and new code follows them too.

1. **A function is a composition of functions.** A public function's body is a short sequence of calls, each to a function that does one thing and is named for it. A reader gets the whole flow from that body and drills into a step only when they need its detail. Each step is built the same way until it is a single operation.
2. **Two exceptions.** Do not extract a step that would be a one-line function. Do not split a performance-critical path where the extra calls cost something measurable.
3. **Callees sit below their callers.** A file runs: constants, public functions in the order a caller uses them, then private helpers in the order they are first called. Reading top-down follows the drill-down.
4. **A comment that labels a phase is a missing function.** `# Authenticate` or `# route to generate tokens` becomes the name of the function that does it.
5. **Data is a struct; state gets a class.** Data is a Pydantic model, a frozen `@dataclass`, an `Enum` or an `Exception` (a `type` in TypeScript); its only methods are derived views of its own fields, such as `Project.members`. A component that owns state across calls (a connection pool, live sockets, background tasks) is a class with behaviour. Which is which is a judgement made by asking what the object holds between calls.
6. **Stateless behaviour is a module-level function.** It takes explicit arguments and returns data, with the `Database` first when it does I/O. This plan removes the indirection that imitates state without holding any: objects built per request only to carry other objects, a `Protocol` or ABC with one implementation, inheritance used to share behaviour.
7. **Dependencies arrive as arguments.** A function or class never reads a global, in its body or as a default argument: config values, clients and keys are passed in, and the call site says what it passes. Only the composition root (`api`: the lifespan and the dependencies) reads `settings`, and it turns config into instances before handing them on: code that needs storage is given the `Database` instance, never a URL or a config section to build one from. The one exception is a module caching its own private global, such as a loaded key.
8. **One home per kind of thing.** Routes live in `api/routers/`. `HTTPException` is raised only in `api/`. Domain errors subclass `utils/exc.py` and are mapped to status codes once. A service's `__init__.py` only re-exports, with `__all__` as strings. Development and test tooling (scripts, generators, performance checks, the mock API) lives in a `dev/` folder: the repository's for tooling that spans both apps, an app's own for tooling only it uses. An app's other folders hold the app and its tests, so the tree shows the architecture and nothing else.
9. **A reputable library beats our own code.** Every line we write is a line to maintain and a line a newcomer reads. Use a well-maintained library wherever it does the job, and write our own only where none does, or where getting the behaviour we need would mean fighting the library. The commit that adds our own code says which of the two it was.
10. **Unchanged from `DESIGN.md`:** the Apache 2.0 licence header on every file, constants at the top, no banner comments, nouns for variables, verbs for functions, `is_`/`should_` for booleans, comments only for what the code cannot say.
11. **A name says what the thing is.** Variables are nouns that name their content: `notice_filter`, never `where`, `kind` or `changes` for a filter. No function is named `build_*`: a thing that is constructed is a class's constructor, and anything else is got, so the function is a `get_*`. `tests/test_styleguide.py` does not count `build` as a verb.
12. **Obvious beats clever.** Write code a reader takes in at a glance: an `if`/`else` that returns each whole literal, one explicit `if` per optional field. Do not make the reader assemble the result in their head from a loop over tuples of fields, a comprehension that builds operators, merged dicts, or one helper that returns two things to be pulled apart. A helper that two callers share is fine when it reads the same way.
13. **Storage is queried in MongoDB's own dialect**: `filter={"user_id": {"$in": [user_id, None]}}`, `update={"$set": {...}}`, `sort=["-created_at"]`, `skip`, `limit`, never structs that wrap each operator. A service function takes its query's arguments or its query model and gets its filter privately; a route never makes one.
14. **What every request reads or writes lives in a cache.** The request log is in Redis, behind a `Database` of its own; records stay in the records' database. Putting per-request data in MongoDB doubled p95 latency.
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

**Every commit is verified the same way.** MSS: `black` and `isort` with no flags, then `pytest > "$LOG" 2>&1; echo "exit=$?" >> "$LOG"`. Dashboard: `eslint`, `tsc`, `vitest`, Playwright. `DESIGN.md` changes in the same commit as any file it names. `dev/e2e_native_test.sh` runs at the end of each step. The style rules a parser can see are tests too: `apps/tergite-mss/tests/test_styleguide.py` and `apps/tergite-dashboard/src/__tests__/styleguide.test.ts`, each with a baseline of the violations that existed when it was added. A commit that fixes a listed violation deletes its line from that baseline, and a commit may never add one.

**Every step ends with a sign-off.** The full-stack e2e and the performance checks are run, and a user or an agent tries the step's changes in the running app and gives the go-ahead before the next step starts.

## What every step keeps

**The auth contract.** Each row has a test in `test_auth.py`, `me/test_my_tokens.py`, `admin/test_projects.py` or `test_auth_contract.py`.

| Surface | Behaviour |
| --- | --- |
| Session JWT | HS256; claims `sub`, `aud`, `roles`; audience `["fastapi-users:auth"]`, which the dashboard mock API and live cookies rely on |
| OAuth state | JWT, audience `fastapi-users:oauth-state`, one-hour lifetime, `next` claim |
| Login | cookie `auth.cookie_name` on `auth.cookie_domain`, `max_age = jwt_ttl`, `httponly`, `secure`, `samesite=lax`; 204, or a redirect to `next` that carries the cookie |
| Logout | active and verified user required; cookie cleared; `{"message": "logged out"}` |
| `POST /me/tokens/` | `{"access_token": …, "token_type": "bearer"}`; `DELETE` returns 204 |
| User dependencies | missing or bad token → 401; inactive user → 401; superuser required → 403 |
| Project dependencies | missing, bad or expired token, or inactive project → 401; strict or system rule with `qpu_seconds <= 0` → 403 "{n} QPU seconds left on project {name}"; system rule without the role → 403 (no route uses the system rule today, so `tests/services/auth/test_access.py` pins it) |
| Invalid project id in a path | 404, not 422 |
| `auth_users` documents | `oauth_accounts` keeps its seven fields; existing documents load unchanged |

**Response bodies** of jobs, devices and every paginated list are compared whole by `test_jobs.py`, `test_devices.py`, `test_calibrations.py` and `me/test_my_jobs.py`, so a `null` field appearing fails them. **CORS:** `Access-Control-Allow-Origin` echoes the request origin on a credentialed request.

**Performance.** Recorded before the refactor, of commit `c0309fd`, and rerun at every step's sign-off:

- MSS: a Locust scenario in `dev/perf/locustfile.py` drives the main read and write routes against MSS from the working tree, with a MongoDB and a Redis of its own, all running natively and seeded from the e2e fixtures. Locust records latency percentiles, throughput, error rate and bytes per request. Alongside it, psutil samples the CPU and memory of the MSS, mongod and redis-server processes, and each database's own status command counts open connections.
- Dashboard: Lighthouse CI (`@lhci/cli`) on the home, devices, device-detail and projects pages against the mock API, configured in `dev/perf/lighthouserc.json`. It records render timings (LCP, TBT), the JavaScript bundle size and network bytes.
- `dev/perf/record.sh <dir>` records both; the baselines live in `dev/perf/baselines/`. `dev/perf/compare.py dev/perf/baselines <dir>` exits 1 when a run's p95 latency, failures, peak memory, connections, bundle size or render timing is more than 10% worse than the baseline; such a step is not signed off until the cause is found. The 10% is a starting threshold, to be tuned once the first runs show how noisy each measure is.

## Step 8: MSS classes and long functions

1. **`BccClient` stays a class**: it owns an `httpx.AsyncClient` per backend. Trim it: the lifespan builds each client with the MSS private key already loaded, so `_create_headers` signs with `self`'s key and 15 methods lose `private_key_file` and `key_password`; drop the unused `files`, `timeout` and `**kwargs` parameters, the unused `base_url` attribute and the copied httpx type hints (687-724). `_request` is split in item 7.
2. **`Emailer` stays a class**: it owns the sweeper's background tasks. Trim it to the one schedule it runs: delete the multi-schedule map and the unused `get_schedule` and `send`; `EmailDetails.to_email_message` becomes its private `_get_email_message(details)`. Start it from the lifespan in `app_kwargs.py`, not from `notices.on_startup`.
3. **`WebsocketConnectionManager` stays a class**: it owns the live device sockets. Move it from `utils/api.py` to `routers/devices`, its only user; delete `broadcast` (unused) and `reply` (it only forwards to `send_json`).
4. **Middleware stays as Starlette subclasses.** `TergiteCORSMiddleware` goes only if stock `CORSMiddleware(allow_origin_regex=".*", allow_credentials=True, …)` passes the CORS test. `EndpointFilter` holds no state, so it becomes a filter function.
5. **`NoticeType(NoticeTypeInfo, Enum)`** → `NoticeTypeId(StrEnum)` plus a `NOTICE_TYPE_INFO: dict[NoticeTypeId, NoticeTypeInfo]` constant. Delete `from_str`, `__str_member_map__`, the `Literal[tuple(…)]` hack and `utils/types.py`. `DeviceEventHandler(Protocol)` → a `Callable` alias.
6. **Behaviour off DTOs**, one service per commit; class-level dunder maps become module constants.
   - `notices`: `CustomNoticeCreate.to_documents` (does I/O) → `_get_custom_notices(db, payload, created_by)`; `Notice.from_template` → `_render_notice`
   - `requests`: `Request.notice_type`, `notice_context`, `from_post_body` and the notice map → `requests/service.py`; `RequestPostBody.target` stays a computed field, as responses carry it, and it and the metadata validator read module constants
   - `devices`: `DeviceEvent.__status_data_map__` → a module constant beside the validator that reads it, as `events.py` imports the DTOs
   - `utils/config.py`: `BccConfig.ip_address` (a DNS lookup in a `computed_field`) → `get_ip_addr(conf.url.host)` at `api/utils.py:87`
   - `jobs`: `JobStatusResponse.from_job` → inline
7. **Long functions become compositions**, one per commit, with unit tests for the pure steps.

| Function | Lines | Composed of |
| --- | --- | --- |
| `bcc` `_request` | 104 | `_send`, `_raise_for_bcc_error(response)` |
| `requests.update` | 94 | `_find_pending_for_approver`, `_record_decision`, `_clear_approver_notices`, `_notify_requesters` |
| `notices.create_system_notice` | 66 | pure `_get_email_status_map(user_ids, preferences, is_email_enabled)`, `_render_notices` |
| `jobs.update_qpu_usage` | 65 | pure `_choose_qpu_notice(before, after, threshold)`, `_notify_project` |
| `email._send_on_repeat` | 64 | `_send_batch(smtp, batch, sender, should_ignore_errors)` |
| `notices.find_many` | 60 | a `NoticeQuery` model shared with `count_many` and `set_read_status_many` (named as `JobQuery` is; "filter" is the Mongo dict) |
| `storage.mongo._to_mongo_json_schema`, renamed `_convert_to_mongo_json_schema` | 57 | `_resolve_ref`, `_translate_keywords` (const, prefixItems, exclusive bounds), `_map_to_bson_type`, `_keep_mongo_keywords` |
| `api/utils.get_verified_device_name` | 56 | `_read_signed_headers`, `_check_client_ip`, pure `_check_nonce_age(timestamp, now, ttl)`, `_check_nonce_unused` |
| `logging.setup_logging` | 56 | `get_log_level(env)` (shared with `settings.py`), `_add_sink`, `_route_std_logging` |
| `notices/emails.process_email_batch_results` | 54 | pure `_partition_results`, `_record_attempts(ids, status)` |
| `notices.clear_notices_by_reference` | 53 | pure `_get_ref_filter(refs, now)`, `_get_cleared_update(timestamp, now)` |

8. **Flatten DTO inheritance** by spelling fields out, JSON unchanged: `DeviceCalibrationLog` (three levels), `Request(RequestPostBody, Document)`, `CreateProjectMetadata(RequestMetadata, ProjectCreate)`.
9. **Last:** remove the four remaining `model_dump` overrides (`utils/api.py:62`, `utils/models.py:43`, `jobs/dtos.py:159`, `devices/dtos.py:94`) and pass the flags at the call sites. The response body tests catch a missed call site.

## Step 9: dashboard

The co-located page hierarchy, the `index / columns / filter-form` table split and loaders beside their pages stay. The two largest hand-written pieces, the API client and the response types mirrored from MSS, become generated code.

1. **Generate the API contract.** `openapi-typescript` generates `src/lib/api/schema.d.ts` from `dev/openapi/openapi.json`, which `dev/openapi/export.py` writes with `npm run generate:api`; CI fails when it is stale. An `openapi-fetch` client in `src/lib/api/client.ts` (base URL, `credentials: "include"`, one error middleware) replaces `authenticatedFetch`, `getQueryString` and `extractError`; it is the only file that talks HTTP. A change to an MSS DTO now fails `tsc` in the dashboard instead of an e2e run.
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
11. **Playwright.** `playwright/utils/records.ts` imports `extendAppToken` and `getUserRequestDetails` from `src/` instead of copying them.

## Step 10: close out

1. Read `DESIGN.md` and both app design docs against the tree. Every path they name exists, and every package has the shape they describe. Today they still name `services/notifications`, `outbox.py` and `request_logging_middleware`, and say there is no code generation from the OpenAPI schema.
2. Run `dev/e2e_native_test.sh` and the performance checks once more against the merged result.
3. Delete this file; the history keeps it.
