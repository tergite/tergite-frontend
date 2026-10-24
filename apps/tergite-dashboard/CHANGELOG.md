# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format {year}.{month}.{patch_number}.

## [Unreleased]

### Added

- Added address completion to the "Admin email" and "Member emails" inputs of the admin
  project forms, so a superuser no longer has to recall an address exactly. It is a
  combobox rather than a `<datalist>`, which Firefox and iOS Safari render only partially,
  and it searches the server on a pause in typing rather than filtering one fetched page.
- Added an unlogged `/health` location to the nginx config for the container healthcheck,
  which used to fetch the whole SPA every ten seconds and fill the access log.
- Added the "Added to project" and "Made project admin" notifications to the bell and to
  the per-type email switches on the settings page.
- Added Approve and Reject buttons to each pending row of the admin requests table, so a
  queue can be cleared without opening every request in turn.
- Added a `/requests` page, under Access in the sidebar, listing the requests the reader has
  made with their status, decision and what was asked for. A requester previously had no way
  to see an outcome except by noticing the notification.
- Added an "Access" group to the sidebar and mobile menu holding Projects and Tokens. Both
  were reachable only from the user menu in the top bar, where a new user never looked.
- Added the low and exhausted QPU-time notifications to the bell and the settings page, so a project
  running out of time is visible before a job is rejected for it.
- Added a `/settings` page, reached from the user menu, with a switch per notification type
  for the email copy. In-app delivery of anything awaiting the reader stays on regardless.
- Added a notifications bell reporting the outcome of project-access and QPU-time requests,
  with approve and reject inline on the ones awaiting the reader. Previously neither
  requester nor approver learned anything without hunting for it.
- Added a "Request project access" dialog on the projects page. It takes a project ID and
  reports an unknown one on the field, so a mistyped ID is self-correcting.
- Added an `/approvals` page where a project admin decides requests for projects they
  administer, reached from a notification or the projects page rather than the nav.
- Added the remaining QPU time of the user's personal project at the foot of the sidebar,
  pointing at the request flow when it is empty.

### Changed

- The user menu no longer repeats Projects and Tokens, which the sidebar now carries. It
  keeps only what lives nowhere else: Settings and Logout.
- The "Request Pending" button on the projects page now carries how much QPU time was
  asked for. A requester had no way to see the figure they had submitted.
- Notices and the notifications bell now show on the admin screens too; they were
  suppressed under `/admin-*`, so an admin saw a notice only after navigating away. The
  API token control stays off those screens, where no project is selected.
- Submitting an access request now confirms with a toast. The dialog simply closed, which
  was indistinguishable from it having been dismissed.
- [BREAKING]: Projects are known by their ID alone, as MSS dropped `ext_id`: the projects
  tables show and filter by it, the access-request form asks for it, and tokens refer to it.
- The projects page's access-request button is now a primary button reading "Request
  access". As a long outline button it neither stood out nor fitted a phone screen.
- The projects page no longer offers Delete on the reader's own personal project, matching
  the API, which refuses it. The admin projects page still offers it, for offboarding.
- Made sidebar and mobile menu scrollable
- [BREAKING]: Notifications and notices are one thing, as in MSS: the bell lists and counts
  the unread ones from `/me/notices/`, the top banner shows the announcements among them, and
  the settings page has one email switch per notice type at `/me/notices/preferences/`.
- [BREAKING]: Notice severities are numbers, as in MSS, so the admin notices card and the top
  banner sort by `severity`.
- [BREAKING]: Requests of every kind, including the admin requests page and QPU time, go
  through `/me/requests/`; the profile, backend control and email lookup moved to
  `/me/profile`, `/admin/bcc/*` and `/admin/users/emails/` along with MSS.

### Fixed

- Logging out now forgets the selected project and API token; they survived the logout, so
  the next user in the same tab started out on the previous user's project.
- Switching project or theme no longer rebuilds the router and remounts every page, which
  threw away open dialogs, form input and scroll position.
- Fixed the device summary's calibration medians, which sorted values as text and counted
  qubits with no value, and the qubit map, which ordered coordinates of 10 and above
  before 2.
- A selected token, project or request now stays selected when its table refetches in a
  different order; selection followed the row position, so the sidebar could switch to
  another item and act on it.
- A row picked while its table refreshes after a delete, create or approval now stays
  picked; the selection was cleared only once the refresh finished, closing its sidebar.
- An error while loading the dashboard or the login page now shows the dashboard's error card
  with working "Try again" and "Back" buttons; the card itself crashed, leaving React Router's
  bare "Unexpected Application Error" page.
- Fixed the days box of the QPU-time request form counting a day as 24 seconds, so 2 days
  asked for 48 seconds on top of the default hour.
- Fixed the QPU-time request form sending a duration other than the one displayed: days,
  hours and seconds showed blank while counting as zero, and emptying a box blocked Submit.

## [2026.06.0] - 2026-06-26

This is part of the tergite release v2026.06.0.

### Added

- Added the control panel screen to switch off backends, initialize recalibration and send out notices
- Added the notices banner on top of the dashboard
- Added the `/privacy.html` and `/terms.html` pages
- Added the footer on the dashboard showing the copy right and privacy and terms of use links

## [2026.06.0-rc.2] - 2026-05-28

### Added

- Added the control panel screen to switch off backends, initialize recalibration and send out notices
- Added the notices banner on top of the dashboard

## [2026.06.0-rc.1] - 2026-05-13

### Added

- Added the `/privacy.html` and `/terms.html` pages
- Added the footer on the dashboard showing the copy right and privacy and terms of use links

## [2026.03.3] - 2026-03-25

- No Change

## [2026.03.2] - 2026-03-23

- No Change

## [2026.03.1] - 2026-03-20

- No Change

## [2026.03.0] - 2026-03-06

- No Change

## [2025.12.0] - 2026-03-16

### Fixed

- Fixed 'dasel: error: unknown flag -r' when run in docker

### Added

- Added the booking calendar to the device details screen

## [2025.09.0] - 2025-10-02

- No change

## [2025.06.2] - 2025-06-17

- No change

## [2025.06.1] - 2025-06-16

- No change

## [2025.06.0] - 2025-06-16

### Changed

- Updated API client code to work with new endpoint structure in MSS
- Updated cypress tests to work with new endpoint structure in MSS
- Updated schema for devices in the fixtures

## [2025.03.1] - 2025-03-18

### Changed

- Updated the full-e2e fixtures to use the latest backend configuration formats

## [2025.03.0] - 2025-03-14

### Changed

- Disabled the "live" switch when creating projects as admin

### Added

- Added dark mode color change on dark mode toggle button click
- Added a dark mode toggle button on the login page
- Added a dark mode toggle button on the dashboard page
- Changed the coloring of the device map chart to use muted connection lines
- Changed the coloring of the device bar chart to use purple bar lines, and muted axes

### Fixed

- Fix project list in nav bar to be only active projects

## [2024.12.2] - 2025-01-22

## [2024.12.1] - 2024-12-20

### Added

- Added `run-nginx.sh` script to help initialize/update the variables like cookie names
  API urls and the like in docker prebuilt containers.

## [2024.12.0] - 2024-12-13

### Added

- Added the tokens list page for viewing, editing and deleting tokens of current user
- Added the projects list page for viewing, requesting QPU time and deleting projects for current user
- Added admin page for viewing, and approving user requests
- Added admin page for viewing, editing, deleting and creating new projects
- Added close button on the job detail drawer on the home page

### Changed

- Changed devices page to show 'no devices found' when no devices are available.
- Changed to show sidebar placeholder on admin user requests page when no user request is selected

### Fixed

## [2024.09.1] - 2024-09-24

### Added

- Added units 'Hz' and 's' to calibration data schema
- Changed all properites of calibration data to be optional
- Added normalizing calibration data to have frequencies in GHz and durations in microseconds

### Changed

### Fixed

## [2024.09.0] - 2024-09-02

### Added

- Initial version
- Device summary list on the dashboard home
- Jobs list on the dashboard home
- Jobs detail drawer on the dashboard home
- Device list page
- Device detail page
- Error page

### Changed

### Fixed
