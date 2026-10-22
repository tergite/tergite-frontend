# UAT: step 0, bug fixes

Run each check and tick it. The step is signed off when every box is ticked, or a failure is
written beside its box.

## Start the app

- Dashboard against the mock API: in `apps/tergite-dashboard`, run `npm run dev`, then open
  <http://127.0.0.1:5173>. The mock API listens on <http://127.0.0.1:8002>.
- MSS on its own (for 0.2, 0.3 and 0.4): in `apps/tergite-mss`, run `./start_mss.sh` with MongoDB
  and Redis running.

## Checks

- [ ] **0.2: a job is readable by its submitter or an admin.** As user A, submit a job with an app
      token and note its `job_id`. With an app token of another, non-admin user B, `GET
      /jobs/<job_id>` and `GET /jobs/<job_id>/status` answer 404, and `GET /jobs/` leaves the job
      out. With user A's token, or an admin's, the job is returned.
- [ ] **0.3: admins can count job submitters.** Logged in as an admin, open
      `/counts/job-submitters?start_utc=2026-01-01T00:00:00Z&end_utc=2027-01-01T00:00:00Z`: it
      returns `{"count": n}`, the number of users who submitted jobs in 2026. Adding
      `&count_distinct=false` counts every job instead. As a non-admin user, the same URL is a 403.
- [ ] **0.4: a malformed request id is a 400.** With an app token for a project that has QPU
      seconds, send a job request with a bad `x-request-id`:

      curl -i -X POST http://127.0.0.1:8002/jobs/ \
        -H "Authorization: Bearer <app token>" -H "x-request-id: not-a-uuid" \
        -H "Content-Type: application/json" -d '{"device": "<a backend name from mss-config.toml>", "calibration_date": "2024-05-23T09:12:00.733Z"}'

      Expect `400` and `{"detail": "The request ID 'not-a-uuid' is not a valid UUID4"}`, not a 500.
- [ ] **0.5: logging out forgets the project.** Log in, choose a project in the top bar, log out,
      then log in again. The project selector starts empty, not on the earlier choice.
- [ ] **0.6: switching theme or project keeps the page.** On the tokens page, open the
      "New token" dialog and type a title. Toggle dark mode, then switch project. The dialog
      stays open with the title still typed. Switching project still reloads the page's data: the
      tokens table shows the new project's tokens.
- [ ] **0.7: calibration numbers order as numbers.** Open a device's detail page. The summary's
      median T1, T2 and readout error sit between the smallest and largest qubit values shown in
      the charts, and the qubit map's columns and rows run 0, 1, 2 … 10, 11, not 0, 1, 10, 11, 2.
- [ ] **0.8: selection follows the item, not the row.** On the tokens page, select a token so the
      sidebar shows it. Create another token, which refetches the table in a new order. The
      sidebar still shows the token you selected.
- [ ] **0.10: load errors show the dashboard's error card.** Stop the mock API (Ctrl-C the `npm
      run dev` terminal and restart only `vite`), then reload <http://127.0.0.1:5173>. The
      dashboard's card appears, with "Try again" and "Back" buttons, instead of a bare
      "Unexpected Application Error". Start the mock API again and press "Try again": the
      dashboard loads.

## Not covered here

- 0.1 changed only `apps/tergite-mss/DESIGN.md`: `/calibrations` stays open, like `/devices`.
- 0.9 removed dead code from the mock API; there is nothing to see.

## Known open item

- `cypress/e2e/admin-projects.cy.ts`, "deleting of project removes project from list, summary and
  top bar", failed once in each of two runs made while MSS tests loaded the machine, and passed
  three times out of three on its own. Rerun it on a quiet machine; if it still fails, suspect the
  route revalidation on project change (`src/router.tsx`).
