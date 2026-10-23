# UAT: step 2, one shape for every MSS service

Step 2 reshapes MSS inside: domain errors, facades, verbs, slim routers, a complete OpenAPI
schema, and settings read only in `api/rest`. The API behaves as before, with one fix: the 400
for too many list query items no longer starts its `detail` with `400: `. Run each check and
tick it. The step is signed off when every box is ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017 and Redis on 6379, and the `.venv` synced with
  `uv sync --all-extras` (step 2 adds pyflakes and drops requests, aiohttp and tomli).

## Checks

- [ ] **2.1–2.13: CI's checks pass.** `.venv/bin/black --check .` and
      `.venv/bin/python -m pyflakes api services utils settings.py tests dev` report nothing, and
      `.venv/bin/pytest tests` (about 18 minutes) gives 966 passed.
- [ ] **2.1: HTTPException stays in the REST layer.**
      `git grep -l HTTPException -- services utils` lists only auth files that step 5 rewrites:
      `services/auth/app_tokens/{auth_backend,authenticator,routers,strategy}.py`,
      `services/auth/projects/routers/__init__.py` and
      `services/auth/users/{authenticator,routers}.py`. `auth_backend.py` and `strategy.py` name
      it only in docstrings.
- [ ] **2.2–2.4: every service has the shape.** `services/jobs/` and `services/calibration/` have
      a `service.py`; each service's `__init__.py` only re-exports, with `__all__` as strings.
      The device event handlers are in `services/devices/events.py`, and
      `git ls-files api/rest/routers/devices` lists only `__init__.py`.
- [ ] **2.5: verbs.**
      `git grep -nE "get_all_devices|get_one_device|try_connect_device|remove_job|toggle_read_status" -- services`
      finds nothing, and `services/calibration/__init__.py` exports `find_latest_calibrations` and
      `create_calibration`. The jobs `get_latest_many` and the route handler names were not in
      2.5's list.
- [ ] **2.6–2.7: routers resolve, call, wrap.** `api/rest/routers/jobs.py` has no BCC client
      lookup, and every alias in `api/rest/dependencies.py` is `Annotated[...]` with a name ending
      in `Dep`.
- [ ] **2.8: the schema describes every body.** `python -m dev.openapi.export` leaves
      `git status` clean, and this prints `0`:
      `jq '[.paths[][].responses | to_entries[] | select(.key | test("^2")) | select(.key != "204") | select((.value.content["application/json"].schema // {}) == {})] | length' dev/openapi/openapi.json`
- [ ] **2.9: utils/api.py holds response shapes only.** The exception handlers are in
      `api/rest/errors.py`, `verify_ws_signature` in `utils/crypto.py`, and every list route
      returns `build_paginated_json(...)`.
- [ ] **2.10–2.11: dead code and dependencies are gone.**
      `grep -nE '"(requests|aiohttp|tomli)' pyproject.toml` finds nothing, and
      `tests/_utils/aiohttp.py` is gone.
- [ ] **2.12: only api/rest reads settings.**
      `git grep -nE "^(import settings|from settings import)" -- services utils` finds nothing.
- [ ] **2.13: no section labels.** `api/rest/__init__.py` has no `# routes` or
      `# exception handlers` comment.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-02 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-02`
      exits 0. In step 1 two runs on unchanged code moved per-route p95 by up to 13 ms and peak
      MongoDB connections by up to 3, past the 10 ms and 2-connection noise floors; if this run
      fails only on such a measure, rerun it once before reading it as a regression.

## Not covered here

- The dashboard is unchanged in step 2; its e2e runs against the mock API, not MSS.
- `dev/e2e_test.sh` needs a clone of tergite-backend; it runs at the end of steps 7 and 9.
