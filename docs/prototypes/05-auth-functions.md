# UAT: step 5, auth, projects and app tokens as functions

Step 5 turns projects and app tokens into plain functions that take the `Database`, and moves
their routes to `api/rest`. App tokens are checked against access rules instead of a
fastapi-users-style authenticator. `services/auth` shrinks from 3,559 to 2,375 lines; the users
keep their fastapi-users structure until steps 6 and 7. The API is unchanged except one fix: an
app token whose user was deleted now gets a 401 instead of a 500. Run each check and tick it.
The step is signed off when every box is ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017, Redis on 6379, the PostgreSQL of step 4 on
  5432 and the `.venv` synced with `uv sync --all-extras`.

## Checks

- [ ] **5.1–5.4: CI's checks pass.** `.venv/bin/black --check .` and
      `.venv/bin/python -m pyflakes api services utils libs migrations settings.py tests dev`
      report nothing, and `.venv/bin/pytest tests` (under a minute) gives 662 passed.
- [ ] **5.1, 5.2: projects and app tokens are functions.** `ls services/auth/projects services/auth/app_tokens`
      lists only `__init__.py`, `dtos.py`, `exc.py` and `service.py`, plus `membership.py` in
      projects. No `database.py`, `manager.py`, `routers/`, `strategy.py` or `auth_backend.py`.
- [ ] **5.3: the authenticator is gone.**
      `git grep -nE "makefun|ProjectBasedAuth|AppTokenAuthenticator|AuthMetadata" -- api services`
      finds only `makefun` in `services/auth/users/authenticator.py`, which step 6 replaces.
- [ ] **5.3: the access rules hold.** `.venv/bin/pytest tests/services/auth/test_access.py -v`
      passes 11 rows: no token or an inactive project is 401; under the strict and system
      rules no QPU seconds is 403 "{n} QPU seconds left on project {name}"; under the system
      rule a user without the role is 403.
- [ ] **5.3: the routes answer as before.** `.venv/bin/pytest tests/api/rest/test_auth_contract.py tests/api/rest/me/test_my_tokens.py tests/api/rest/me/test_my_projects.py tests/api/rest/admin -v`
      passes, including `test_app_token_of_deleted_user_fails`.
- [ ] **5.4: no service keeps a `Database`.** `git grep -n "_database\b" -- services` finds
      nothing.
- [ ] **5.5: the API contract is unchanged.**
      `git diff 1b5318b -- dev/openapi/openapi.json` changes only four route descriptions:
      the three job reads name their `owner` argument, and removing a member says it revokes
      their app tokens.
- [ ] **The docs say where auth stands.** REFACTOR.md step 5 records what was built and why
      it differs from the plan; MSS's `DESIGN.md` §1 and §3 describe the access rules and the
      query dependencies.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-05 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-05`
      exits 0, or fails only as step 4 did: a p95 within 13 ms of the baseline, or peak
      MongoDB connections near 27 against 17, from the client Beanie's users keep until step 7.
      **2026-10-24: fails only on MongoDB connections, 29 against 17** (26 at step 3, 27 at
      step 4). No request failed. Every p95 is within 13 ms: GET `/me/profile` 27 ms against
      17, GET `/me/tokens/` 25 against 17, GET `/me/projects/` 26 against 19.

## Not covered here

- `GET /jobs/` and `GET /me/jobs/` document their `result` and `timestamps` filters as a
  request body, as `JobQuery` is injected with `Depends()` and those fields are models. The projects and app tokens lists avoid this with
  explicit query dependencies; `JobQuery` is not changed here.
- The users, their manager and the JWT routes: steps 6 and 7.
