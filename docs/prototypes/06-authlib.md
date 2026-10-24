# UAT: step 6, `libs/authlib`

Step 6 copies fastapi-users 14.0.2 into `libs/authlib`, strips what tergite never calls, adds
what MSS bolts on, keeps users in a `Database`, and reshapes the rest into functions around
one configured `Auth`. It is 1,012 lines against upstream's 2,926. MSS does not use it yet:
step 7 switches to it, so no route, response or stored record changes here. `libs/storage`
gains one feature for it, lists of models matched with `$elemMatch`. Run each check and tick
it. The step is signed off when every box is ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017, Redis on 6379, the PostgreSQL of step 4 on
  5432 and the `.venv` synced with `uv sync --all-extras` (step 6 adds asgi-lifespan to the
  dev extras).

## Checks

- [ ] **6.1–6.7: CI's checks pass.** `.venv/bin/black --check .`, `.venv/bin/isort --check-only .`
      and `.venv/bin/python -m pyflakes api services utils libs migrations settings.py tests dev`
      report nothing, and `.venv/bin/pytest tests` (under a minute) gives 729 passed.
- [ ] **6.1: the licence is kept.** `libs/authlib/LICENSE` is upstream's MIT licence, every
      file derived from it names fastapi-users in its header (all but the new
      `providers.py`), and MSS's `CREDITS.md` credits it.
- [ ] **6.2, 6.5: only what tergite uses is left.** `ls libs/authlib` lists `auth.py`,
      `cookies.py`, `errors.py`, `models.py`, `providers.py`, `routers.py`, `schemas.py`,
      `tokens.py` and `users.py`: no password, register, reset, verify, users or associate
      routes, no database or Redis token strategy, and
      `git grep -nE "import .*HTTPException|HTTPException\(|makefun|fastapi_users" -- libs/authlib`
      finds nothing.
- [ ] **6.3: lists of models work on every store.**
      `.venv/bin/pytest tests/libs/storage/test_conformance.py -k list_of_models -v` passes 6:
      an account is matched by `$elemMatch` on one element only, never across two, and a list
      of models is set whole, with `$addToSet` and plain matches refused.
- [ ] **6.3, 6.7: the account-linking rule holds on MongoDB and SQLite.**
      `.venv/bin/pytest tests/libs/authlib/test_users.py -v` passes: an account's user gets its
      new token; a user of the email is refused unless the provider links by email, and linked
      with the provider's roles when it does; a new email creates a user, verified as the
      provider says; an email off the provider's pattern is not permitted.
- [ ] **6.4, 6.5: the routes behave as MSS's do.** `.venv/bin/pytest tests/libs/authlib -v`
      passes 56, among them: the session token from the header, else the cookie; the roles
      claim; the user id without the database; the 403 for a missing role; `/{provider}/…`
      and `/app/{provider}/…`; auto-authorize and the `next` redirect; logout's
      `{"message": "logged out"}`.
- [ ] **6.7: the audiences are fastapi-users' own.** `test_a_session_token_names_the_user_and_roles`
      and `test_the_state_is_for_fastapi_users_oauth_state` in `tests/libs/authlib/test_tokens.py`
      decode with `fastapi-users:auth` and `fastapi-users:oauth-state`.
- [ ] **The styleguide baseline holds no authlib line.**
      `grep -c libs/authlib tests/fixtures/styleguide_baseline.txt` prints 0.
- [ ] **The docs say where auth stands.** REFACTOR.md step 6 records what was built, and step 7
      says its items 1 and 3 land together and which OpenAPI changes the switch brings.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-06 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-06`
      exits 0, or fails only as steps 4 and 5 did: a p95 within 13 ms of the baseline, or peak
      MongoDB connections near 29 against 17, from the client Beanie's users keep until step 7.
      **2026-10-24: holds.** It fails only on such measures: p95 of GET `/me/profile` 28 ms
      against 17 and GET `/me/projects/` 30 against 19, each within 13 ms, and peak MongoDB
      connections 27 against 17 (29 at step 5). No request failed.

## Not covered here

- MSS on `authlib`, its users as storage records, and the API tests on every database: step 7.
