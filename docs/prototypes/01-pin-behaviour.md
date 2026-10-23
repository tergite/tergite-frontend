# UAT: step 1, pin behaviour with tests

Step 1 adds tests and moves tooling; the apps behave as before. Run each check and tick it. The
step is signed off when every box is ticked, or a failure is written beside its box.

## Start the app

- Dashboard against the mock API: in `apps/tergite-dashboard`, run `npm run dev`, then open
  <http://127.0.0.1:5173>. The mock API, now in `dev/mock-api/`, listens on
  <http://127.0.0.1:8002>. The mock login page takes any fixture email, e.g. `john.doe@example.com`.
- MSS tests: in `apps/tergite-mss`, with MongoDB on 27017 and Redis on 6379.

## Checks

- [ ] **1.1–1.5: the MSS suite passes.** In `apps/tergite-mss`, run
      `.venv/bin/pytest tests` (about 17 minutes). Expect 961 passed. It includes
      `tests/api/rest/test_auth_contract.py` (16 tests, one per auth contract row) and
      `tests/api/rest/test_cors.py`.
- [ ] **1.5: conftest keeps only the core.** `tests/conftest.py` holds the environment, the stores,
      the client and the shared records; the OAuth fixtures are in `tests/_utils/oauth.py`, the
      mock BCC fixtures in `tests/_utils/mock_backend.py`.
- [ ] **1.6: every feature has an e2e spec.** `apps/tergite-dashboard/DESIGN.md` §6 lists each
      feature beside its spec. In `apps/tergite-dashboard`, `npm run e2e` passes every spec,
      `approvals.cy.ts` included.
- [ ] **1.6: approvals by hand.** Log in as `david.doe@example.com`, a project admin. The projects
      page shows "1 awaiting your approval"; the link opens `/approvals` with julie.doe's access
      request. Approve it: the sidebar returns to its placeholder, the row reads "approved", and
      the projects page no longer shows the count.
- [ ] **1.7: the baselines are recorded.** `dev/perf/baselines/` holds `locust_stats.csv`,
      `docker-stats.csv`, `connections.csv` and `lighthouse/`. With docker running and port 8002
      free, `./dev/perf/record.sh /tmp/perf-01 && python3 dev/perf/compare.py dev/perf/baselines
      /tmp/perf-01` prints every measure and exits 0. Note any measure that moved more than 10%:
      that is the noise the threshold has to absorb.
- [ ] **1.8: `docs/prototypes/README.md`** says the folder holds these scripts and goes at step 10.
      `docs/rfcs/` is gone, and the root `DESIGN.md` no longer links to it.
- [ ] **1.9: tooling lives in `dev/`.** `e2e_test.sh` is at `dev/e2e_test.sh`, the mock API at
      `apps/tergite-dashboard/dev/mock-api/`, and `npm run dev` above started it from there. No
      `api/` folder is left at the dashboard's root.

## Not covered here

- 1.2: the response bodies were already pinned by whole-body tests (`test_jobs.py`,
  `test_devices.py`, `test_calibrations.py`, `me/test_my_jobs.py`).
- `dev/e2e_test.sh` needs a clone of tergite-backend; it runs at the end of steps 7 and 9.
