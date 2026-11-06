import type { Locator, Page } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import type {
  Booking,
  Device,
  Job,
  Project,
  User,
} from "./types";

const CURRENT_DATE = process.env.CURRENT_DATE!;
const REFETCH_INTERVAL_MS = parseFloat(process.env.VITE_REFETCH_INTERVAL_MS!);
const API_URL = process.env.VITE_API_BASE_URL;
const MAX_BOOKINGS = 5;
const JOB_TABLE_HEADERS = ["Job ID", "Device", "Duration", "Created at", "Status"];
const BOOKING_TABLE_HEADERS = ["Device", "Starts in", "Duration"];
const LAST_ONLINE_PATTERN =
  /\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i;
const CREATED_AT_PATTERN = /\d+ \w+ \d+, \d+:\d+ ?(AM)|(PM)?/i;
const DURATION_PATTERN =
  /(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+/i;
const SHORT_DURATION_PATTERN = /(\d+ (secs?)|(mins?)|(hrs?)|(days?)|(wks?)|(mths?)|(yrs?),?)+/i;

// an admin with projects, a member of several, and a user of none
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "paul.doe@example.com", "julie.doe@example.com"].includes(v.email),
);
const devices = readFixture<Device[]>("device-list");
const jobs = readFixture<Job[]>("jobs");
const projects = readFixture<Project[]>("projects");

const visibleDevices = devices.slice(0, 3);
const onlineDevices = devices.filter((v) => v.is_online);

for (const user of users) {
  const userProjects = projects.filter((v) => v.user_ids.includes(user.id) && v.is_active);
  const username = user.email.split("@")[0];
  const allUserJobs = jobs
    .filter((v) => v.user_id === user.id)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

  test.describe(`home page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await page.clock.setFixedTime(CURRENT_DATE);
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        waitForApi(page, "GET", "/devices/"),
        waitForApiTimes(page, "GET", "/bookings/", devices.length),
        loginAs(user, "./"),
      ]);
    });

    test("renders the device online status chart", async ({ page }) => {
      const percentOnline = Math.round((onlineDevices.length / devices.length) * 100);
      const chart = page
        .locator("#devices-online-piechart")
        .locator("svg", { hasText: `${percentOnline}%` });
      await expect(chart).toHaveAttribute("aria-valuenow", `${percentOnline}`);
    });

    test("renders the first 3 devices", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const card = page.locator("#devices-table");

      await expectTable(
        card,
        ["Device", "Qubits", "Status", "Last Seen"],
        visibleDevices.map((device) => [
          device.name,
          `${device.number_of_qubits}`,
          device.is_online ? /online/i : /offline/i,
          device.last_online ? LAST_ONLINE_PATTERN : /N\/A/i,
        ]),
      );
    });

    test("renders the list of all user's jobs with no project selected", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const card = page.locator("#jobs-table", { hasText: /all projects/i });

      await expectTable(card, JOB_TABLE_HEADERS, allUserJobs.map(toJobCells));
    });

    test("renders the list of user's jobs in selected project", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      for (const project of userProjects) {
        await page.locator('[data-testid="topbar"] button', { hasText: /project:/i }).click();
        await page.locator('#project-selector [role="option"]', { hasText: project.name }).click();

        const card = page.locator("#jobs-table", {
          has: page.getByText(project.name, { exact: true }),
        });
        const projectJobs = allUserJobs.filter((v) => v.project_id === project.id);
        await expectTable(card, JOB_TABLE_HEADERS, projectJobs.map(toJobCells));
      }
    });

    test("renders the list of all upcoming bookings, ignoring any unavailable devices", async ({
      page,
      apiUrl,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const unavailableDevices = devices.filter((_v, idx) => idx % 2 === 0);
      const availableDevices = devices.filter((_v, idx) => idx % 2 === 1);
      for (const device of unavailableDevices) {
        await page.route(`${API_URL}/bookings/${device.name}*`, (route) =>
          route.fulfill({ status: 503, json: { detail: "Device is offline" } }),
        );
      }

      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        waitForApi(page, "GET", "/devices/"),
        waitForApiTimes(page, "GET", "/bookings/", devices.length),
        page.goto("./"),
      ]);

      const card = page.locator("#bookings-table");
      const bookings = await fetchUpcomingBookings(page, apiUrl, user, availableDevices);
      await expectTable(
        card,
        BOOKING_TABLE_HEADERS,
        bookings.map((booking) => [
          booking.backend,
          DURATION_PATTERN,
          booking.total_duration ? SHORT_DURATION_PATTERN : /N\/A/i,
        ]),
      );
    });

    test("refreshes device list every after the refresh interval", async ({ page }) => {
      await expectRefetches(countApiResponses(page, "GET", "/devices/"), 3);
    });

    test("refreshes jobs list every after the refresh interval", async ({ page }) => {
      await expectRefetches(countApiResponses(page, "GET", "/me/jobs/"), 3);
    });

    test("refreshes bookings list every after the refresh interval", async ({ page }) => {
      await expectRefetches(countApiResponses(page, "GET", "/bookings/"), 3 * devices.length);
    });

    test("filters the list of jobs", async ({ page }) => {
      const filterMaps = [
        {
          input: { device: "lo" },
          result: allUserJobs.filter((v) => v.device.toLowerCase().startsWith("lo")),
        },
        {
          input: { device: "lo", job_id: "1" },
          result: allUserJobs.filter(
            (v) => v.device.toLowerCase().startsWith("lo") && v.job_id.startsWith("1"),
          ),
        },
        {
          input: { job_id: "6" },
          result: allUserJobs.filter((v) => v.job_id.startsWith("6")),
        },
        {
          input: { device: "lo", status: "failed" },
          result: allUserJobs.filter(
            (v) => v.device.toLowerCase().startsWith("lo") && v.status === "failed",
          ),
        },
        {
          input: { status: "pending" },
          result: allUserJobs.filter((v) => v.status === "pending"),
        },
        {
          input: { status: "successful" },
          result: allUserJobs.filter((v) => v.status === "successful"),
        },
        {
          input: { device: "lo", status: "pending", job_id: "4" },
          result: allUserJobs.filter(
            (v) =>
              v.device.toLowerCase().startsWith("lo") &&
              v.job_id.startsWith("4") &&
              v.status === "pending",
          ),
        },
      ];

      await page.setViewportSize({ width: 1080, height: 750 });
      const table = page.locator("#jobs-table table");
      const form = page.locator("[data-cy-filter-form]");
      await openFilterForm(page.locator("#jobs-table [aria-label='Filter']"), form);

      for (const { input, result } of filterMaps) {
        if (input.job_id) await form.locator("input[name='job_id']").pressSequentially(input.job_id);
        if (input.device) await form.locator("input[name='device']").pressSequentially(input.device);
        if (input.status) {
          await form.locator("button[role='combobox']").click();
          await page
            .locator("[data-cy-job-status-select]")
            .getByText(new RegExp(input.status, "i"))
            .first()
            .click();
        }
        await form.locator("button[type='submit']").click();
        await expectJobIdsListed(table, result);

        await form.locator("button[type='reset']").click();
        await expectJobIdsListed(table, allUserJobs);
      }
    });

    test("renders the details of each job", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const table = page.locator("table", { hasText: /Job ID/i }).first();

      for (const job of allUserJobs) {
        await table.locator("tr td:first-child", { hasText: job.job_id }).first().click();

        const drawer = page.locator("[data-cy-job-detail]", { hasText: /details about this job/i });
        const details = [
          new RegExp(`Job:\\s?${job.job_id}`, "i"),
          new RegExp(`Status:\\s?${job.status}`, "i"),
          /Created at:\s?\d+ \w+ \d+, \d+:\d+ ?(AM)|(PM)?/i,
          new RegExp(`Device:\\s?${job.device}`, "i"),
          job.duration_in_secs
            ? /Duration:\s?(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+/i
            : /Duration:\s?N\/A/i,
          ...(job.failure_reason ? [new RegExp(`Error:\\s?${job.failure_reason}`, "i")] : []),
        ];
        for (const detail of details) {
          await expect(drawer.getByText(detail).first()).toBeVisible({ timeout: 10_000 });
        }

        await drawer.locator('button[aria-label="X"]').click();
      }
    });

    test("filters the list of upcoming bookings", async ({ page, apiUrl }) => {
      const bookings = await fetchUpcomingBookings(page, apiUrl, user, devices);
      const filterMaps = [
        {
          input: { backend: "lo" },
          result: bookings.filter((v) => v.backend.toLowerCase().startsWith("lo")),
        },
        {
          input: { backend: "pin" },
          result: bookings.filter((v) => v.backend.toLowerCase().startsWith("pin")),
        },
        {
          input: { backend: "l" },
          result: bookings.filter((v) => v.backend.toLowerCase().startsWith("l")),
        },
      ];

      await page.setViewportSize({ width: 1080, height: 750 });
      const table = page.locator("#bookings-table table");
      const form = page.locator("[data-cy-filter-form]");
      await openFilterForm(page.locator("#bookings-table button[aria-label='Filter']"), form);

      for (const { input, result } of filterMaps) {
        await form.locator("input[name='backend']").pressSequentially(input.backend);
        await form.locator("button[type='submit']").click();
        await expectBookingsListed(table, result);

        await form.locator("button[type='reset']").click();
        await expectBookingsListed(table, bookings);
      }
    });
  });
}

/** Waits for the response to the count-th request with the method whose path starts with the given one */
function waitForApiTimes(page: Page, method: string, pathPrefix: string, count: number) {
  let seen = 0;
  return page.waitForResponse(
    (response) =>
      response.request().method() === method &&
      new URL(response.url()).pathname.startsWith(pathPrefix) &&
      ++seen === count,
  );
}

function countApiResponses(page: Page, method: string, pathPrefix: string): () => number {
  let count = 0;
  page.on("response", (response) => {
    if (
      response.request().method() === method &&
      new URL(response.url()).pathname.startsWith(pathPrefix)
    ) {
      count++;
    }
  });
  return () => count;
}

/** Expects each of the next responses to come within one and a half refresh intervals of the last */
async function expectRefetches(countResponses: () => number, total: number) {
  for (let expected = 1; expected <= total; expected++) {
    await expect
      .poll(countResponses, { timeout: 1.5 * REFETCH_INTERVAL_MS, intervals: [50] })
      .toBeGreaterThanOrEqual(expected);
  }
}

async function fetchUpcomingBookings(
  page: Page,
  apiUrl: string,
  user: User,
  devices: Device[],
): Promise<Booking[]> {
  const bookingsPerDevice = await Promise.all(
    devices.map(async (device) => {
      const response = await page.request.get(
        `${apiUrl}/bookings/${device.name}?user_id=${user.id}&min_start_utc=${CURRENT_DATE}&sort=start_utc`,
      );
      return (await response.json()).data as Booking[];
    }),
  );
  return bookingsPerDevice
    .flat()
    .sort((a, b) => Date.parse(a.start_utc) - Date.parse(b.start_utc))
    .slice(0, MAX_BOOKINGS);
}

/** Expects the table in the container to have the headers, and the rows or else a 'no results' row */
async function expectTable(container: Locator, headers: string[], rows: (string | RegExp)[][]) {
  await expect(container.locator("thead th")).toHaveText(headers);

  const bodyRows = container.locator("tbody tr");
  await expect(bodyRows).toHaveCount(rows.length || 1);
  if (rows.length === 0) {
    await expect(bodyRows.locator("td", { hasText: /no results/i })).toBeVisible();
  }
  for (const [idx, cells] of rows.entries()) {
    await expect(bodyRows.nth(idx).locator("td")).toHaveText(cells);
  }
}

async function openFilterForm(filterButton: Locator, form: Locator) {
  await filterButton.click();
  // the form resets its fields on opening, wiping anything typed before; the popover focuses them after
  await expect(form.locator("input").first()).toBeFocused();
}

async function expectJobIdsListed(table: Locator, jobs: Job[]) {
  await expect(table.locator("tbody tr")).toHaveCount(jobs.length || 1);
  for (const job of jobs) {
    await expect(table.locator("tr td:first-child", { hasText: job.job_id }).first()).toBeVisible();
  }
}

async function expectBookingsListed(table: Locator, bookings: Booking[]) {
  await expect(table.locator("tbody tr")).toHaveCount(bookings.length || 1);
  for (const [idx, booking] of bookings.entries()) {
    const cell = table.locator(
      `tr:nth-child(${idx + 1}) td:first-child div[data-booking-id="${booking.id}"]`,
      { hasText: booking.backend },
    );
    await expect(cell).toBeVisible();
  }
}

function toJobCells(job: Job): (string | RegExp)[] {
  return [
    job.job_id,
    job.device,
    job.duration_in_secs ? DURATION_PATTERN : /N\/A/i,
    CREATED_AT_PATTERN,
    job.status,
  ];
}
