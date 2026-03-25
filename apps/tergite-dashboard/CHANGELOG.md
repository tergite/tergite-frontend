# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project follows versions of format {year}.{month}.{patch_number}.

## [Unreleased]

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
