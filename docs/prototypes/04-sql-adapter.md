# UAT: step 4, the SQL adapter

Step 4 adds `SqlStore`, a storage backend for any SQLAlchemy URL with an async driver, with
the tables derived from the schemas and migrated by Alembic. MSS itself still runs on MongoDB:
Beanie keeps the users at `database.url` until step 7, so the API tests stay on MongoDB and
move onto every database in step 7.4. Two behaviours change on MongoDB: an expired record is no
longer read while the TTL monitor has yet to delete it, and an update can no longer give a
record another key. Run each check and tick it. The step is signed off when every box is
ticked, or a failure is written beside its box.

## Start

- In `apps/tergite-mss`, with MongoDB on 27017, Redis on 6379 and the `.venv` synced with
  `uv sync --all-extras` (step 4 adds sqlalchemy, asyncpg, aiosqlite and alembic).
- A PostgreSQL for the tests:
  `docker run -d --name tergite-mss-test-postgres -e POSTGRES_USER=tergite -e POSTGRES_PASSWORD=tergite -e POSTGRES_DB=tergite_test -p 5432:5432 postgres:17`.
  `TEST_POSTGRES_URL` points the tests at another.

## Checks

- [ ] **4.1–4.6: CI's checks pass.** `.venv/bin/black --check .` and
      `.venv/bin/python -m pyflakes api services utils libs migrations settings.py tests dev`
      report nothing, and `.venv/bin/pytest tests` (under a minute) gives 647 passed.
- [ ] **4.1: only the store names SQL.**
      `git grep -lE "sqlalchemy|asyncpg|aiosqlite" -- api services utils libs` lists only
      `libs/storage/sql/*` and `libs/storage/database.py`, whose comment gives
      `postgresql+asyncpg://` as an example of the URLs it routes there.
- [ ] **4.1: every store behaves alike.** `.venv/bin/pytest tests/libs/storage/test_conformance.py -v`
      runs each test as `[mongodb]`, `[postgresql]` and `[sqlite]`, and all pass, including
      MongoDB's null matching for `$ne`, `$in` and `$nin`, and the refusal to change a key.
- [ ] **4.1: no caller's value reaches SQL text.**
      `test_filter_values_are_bound_parameters_never_sql_text` in
      `tests/libs/storage/sql/test_sql_translation.py` passes: a hostile string is only in the
      bound parameters of the compiled query.
- [ ] **4.2: every service runs on each database.** `.venv/bin/pytest tests/services -v`
      runs projects, app tokens, jobs, devices, calibrations, notices and requests on all
      three, and all pass. Projects keep members in `auth_project_user_ids`, notices their
      dismissals in `notice_dismissed_by`, requests their targets in `request_target_user_ids`.
- [ ] **4.3: SQL expires records without a TTL index.**
      `.venv/bin/pytest tests/libs/storage/sql/test_sql_store.py` passes: an expired record is
      not read, and the sweep deletes it.
- [ ] **4.4: the migrations make the schemas' tables.** `.venv/bin/pytest tests/test_migrations.py`
      passes, and `migrations/versions/` holds one revision. `start_mss.sh` runs
      `alembic upgrade head` when `database.url` has a `+driver` scheme.
- [ ] **4.6: the docs say where SQL stands.** MSS's `DESIGN.md` §5 describes the three
      stores and the SQL tables, and `mss-config.example.toml` lists the URL schemes and that
      MSS runs on MongoDB alone until its users move off Beanie.
- [ ] **The baselines still hold.** With docker running and port 8002 free,
      `./dev/perf/record.sh /tmp/perf-04 && python3 dev/perf/compare.py dev/perf/baselines /tmp/perf-04`
      exits 0. Step 3 signed off with peak MongoDB connections at 26 against 17, from the
      second client Beanie's users keep until step 7; if this run fails only on that, or on a
      p95 within 13 ms of the baseline, it holds as step 3 did.
      **2026-10-24: holds.** The run fails only on such measures: p95 of GET `/jobs/` 68 ms
      against 56, GET `/me/notices/` 35 against 22 and GET `/me/projects/` 30 against 19,
      each within 13 ms, and peak MongoDB connections 27 against 17 (26 at step 3). No request
      failed, and every other route is within its noise floor.

## Not covered here

- The API tests on PostgreSQL and SQLite, and an app running on SQL: step 7.
- Moving an existing deployment's data from MongoDB to SQL needs an export/import script,
  which no step of the plan includes.
