import { type Page, type Request } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { type Device, type User, UserRole } from "../types";

// the stored shape, with offsets in hours from now for the timestamps
interface NoticeFixture {
  id: string;
  type: string;
  starts_at_offset_hours: number | null;
  expires_at_offset_hours: number | null;
}

// the admin, and a user the page is forbidden to
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "john.doe@example.com"].includes(v.email),
);
const devices = readFixture<Device[]>("device-list");
// the admin's notices card lists every custom notice in force, whoever it is for
const activeNoticeCount = readFixture<NoticeFixture[]>("notices").filter(
  (v) =>
    v.type.startsWith("custom") &&
    (v.starts_at_offset_hours ?? 0) <= 0 &&
    (v.expires_at_offset_hours ?? 0) >= 0,
).length;

const totalDeviceCount = devices.length;
const onlineDeviceCount = devices.filter((d) => d.is_online).length;

// selected on page load
const defaultDevice = devices[0];
const onlineDevice = devices.find((d) => d.is_online)!;

for (const user of users) {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = user.email.split("@")[0];

  test.describe(`admin control page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      const loaded =
        isAdmin &&
        Promise.all([
          waitForApi(page, "GET", "/me/projects/"),
          waitForApi(page, "GET", "/devices/"),
        ]);
      await loginAs(user, "/admin-control");
      await loaded;
    });

    if (!isAdmin) {
      test("redirects non-admin users away from the control panel", async ({ page }) => {
        await expect(page).not.toHaveURL(/\/admin-control/);
      });
    } else {
      test.beforeEach(async ({ page, apiUrl }) => {
        // tests take it offline
        await page.request.post(`${apiUrl}/admin/bcc/switch/${onlineDevice.name}/on`);
      });

      test("renders the control panel header with a live device count badge", async ({ page }) => {
        await expect(page.locator("h1", { hasText: /control panel/i })).toBeVisible();
        await expect(
          page.getByText(`${onlineDeviceCount}/${totalDeviceCount} online`).first(),
        ).toBeVisible();
      });

      test("renders the system status bar with total, online, and selected device tiles", async ({
        page,
      }) => {
        const label = page.locator("#system-status-bar #status-label");
        const value = page.locator("#system-status-bar #status-value");
        await expect(label.filter({ hasText: /^Devices$/ }).first()).toBeVisible();
        await expect(value.filter({ hasText: `${totalDeviceCount}` }).first()).toBeVisible();

        await expect(label.filter({ hasText: /^Online$/ }).first()).toBeVisible();
        await expect(value.filter({ hasText: `${onlineDeviceCount}` }).first()).toBeVisible();

        await expect(label.filter({ hasText: /^Selected$/ }).first()).toBeVisible();
        await expect(value.filter({ hasText: defaultDevice.name }).first()).toBeVisible();
      });

      test("shows a device selector when there are multiple devices", async ({ page }) => {
        await expect(deviceSelector(page)).toBeVisible();
      });

      test("switches the focused device when a different device is chosen", async ({ page }) => {
        await selectDevice(page, onlineDevice.name);

        const selectedTile = page
          .locator("#status-label", { hasText: /^Selected$/ })
          .first()
          .locator("..");
        await expect(selectedTile.getByText(onlineDevice.name).first()).toBeVisible();
        await expect(
          backendCard(page).locator("p", { hasText: onlineDevice.name }).first(),
        ).toBeVisible();
      });

      test("shows the device name, qubit count, version, and Online/Offline badge", async ({
        page,
      }) => {
        await expect(backendCard(page).filter({ hasText: /backend control/i })).toBeVisible();
        await expect(
          backendCard(page)
            .filter({ hasText: /offline/i })
            .first(),
        ).toBeVisible();
        await expect(backendCard(page).filter({ hasText: defaultDevice.name })).toBeVisible();
        await expect(
          backendCard(page).filter({ hasText: String(defaultDevice.number_of_qubits) }),
        ).toBeVisible();
        await expect(backendCard(page).filter({ hasText: defaultDevice.version })).toBeVisible();
      });

      test("displays the toggle in the OFF position and 'Backend disabled' label for an offline device", async ({
        page,
      }) => {
        await expect(backendCard(page).filter({ hasText: /backend disabled/i })).toBeVisible();
        await expect(
          backendCard(page).filter({ hasText: /not accepting new jobs/i }),
        ).toBeVisible();
        await expect(backendToggle(page)).toHaveAttribute("aria-checked", "false");
      });

      test("brings an offline backend online immediately on toggle click (no confirmation)", async ({
        page,
      }) => {
        const card = backendCard(page);
        const toggle = backendToggle(page);
        await expect(toggle).toHaveAttribute("aria-checked", "false");
        await Promise.all([waitForApi(page, "POST", "/admin/bcc/switch/"), toggle.click()]);
        await expect(card.getByText(/take backend offline\?/i)).toHaveCount(0);

        await expect(card.getByText(/backend enabled/i).first()).toBeVisible();
        await expect(card.getByText(/accepting jobs from all users/i).first()).toBeVisible();
        await expect(toggle).toHaveAttribute("aria-checked", "true");
      });

      test("requires confirmation before taking an online backend offline", async ({ page }) => {
        const switchOffs = recordRequests(page, "POST", /\/admin\/bcc\/switch\/.+\/off$/);
        await selectDevice(page, onlineDevice.name);

        const enabledLabel = backendCard(page).locator("label", { hasText: /backend enabled/i });
        const toggle = backendToggle(page);
        const dialog = page.getByTestId("confirmation-dialog");

        await expect(enabledLabel).toBeVisible();
        await expect(toggle).toHaveAttribute("aria-checked", "true");

        await toggle.click();
        await expect(dialog.filter({ hasText: /take backend offline\?/i })).toBeVisible();

        await dialog.locator("button", { hasText: /^Cancel$/i }).click();
        expect(switchOffs).toHaveLength(0);
        await expect(enabledLabel).toBeVisible();

        await toggle.click();
        await Promise.all([
          waitForApi(page, "POST", "/admin/bcc/switch/"),
          dialog.locator("button", { hasText: /take offline/i }).click(),
        ]);
        await expect(
          backendCard(page).locator("label", { hasText: /backend disabled/i }),
        ).toBeVisible();
        await expect(toggle).toHaveAttribute("aria-checked", "false");
      });

      test("shows calibration metrics (T1, T2, qubits) for the selected device", async ({
        page,
      }) => {
        const card = page.getByTestId("calibration-card");
        await expect(card.locator("p", { hasText: /^Calibration$/i }).first()).toBeVisible();
        await expect(card.filter({ hasText: defaultDevice.name })).toBeVisible();
        await expect(card.filter({ hasText: /median t1/i })).toBeVisible();
        await expect(card.filter({ hasText: /median t2/i })).toBeVisible();
        await expect(card.filter({ hasText: /qubits/i })).toBeVisible();
      });

      test("triggers recalibration only after the confirmation dialog is accepted", async ({
        page,
      }) => {
        const recalibrations = recordRequests(
          page,
          "POST",
          /\/admin\/bcc\/recalibration\/.+\/init/,
        );
        await expect(page.getByTestId("calibration-card")).toContainText(/median t1/i);

        const trigger = page.locator("button", { hasText: /trigger recalibration/i });
        await trigger.click();
        await expect(page.getByText(/trigger recalibration\?/i).first()).toBeVisible();

        await page.locator("button", { hasText: /^Cancel$/i }).click();
        expect(recalibrations).toHaveLength(0);

        await trigger.click();
        await Promise.all([
          waitForApi(page, "POST", "/admin/bcc/recalibration/"),
          page.locator("button", { hasText: /start calibration/i }).click(),
        ]);
        await expect(page.getByText(/recalibration started/i).first()).toBeVisible();
      });

      test("renders the notices card with a 'New notice' form", async ({ page }) => {
        await expect(page.getByText(/^Notices$/i).first()).toBeVisible();
        await expect(page.getByText(/new notice/i).first()).toBeVisible();
        await expect(page.locator("textarea#notice-message")).toBeVisible();
        await expect(page.getByText(/info/i).first()).toBeVisible();
      });

      test(`shows the correct active notice count badge (expected: ${activeNoticeCount})`, async ({
        page,
      }) => {
        await expect(page.getByText(`${activeNoticeCount} active`).first()).toBeVisible();
      });

      test("keeps the Post button disabled until the message textarea has content", async ({
        page,
      }) => {
        const post = page.locator("button", { hasText: /^Post$/i });
        await expect(post).toBeDisabled();
        await page.locator("textarea#notice-message").fill("Planned downtime window.");
        await expect(post).toBeEnabled();
      });

      test("shows active notices with severity labels visible to the current user", async ({
        page,
      }) => {
        await expect(page.getByLabel("Delete notice").first()).toBeVisible();
        await expect(page.getByText(/\b(info|warning|critical)\b/i).first()).toBeVisible();
      });

      test("shows the active notice banner on an admin screen too", async ({ page }) => {
        const banner = page.getByTestId("top-banner");
        await expect(banner).toBeVisible();
        await expect(banner.getByLabel("Dismiss notice").first()).toBeVisible();
        // no project is selected here, so no API token
        await expect(banner.locator("input#api-token")).toHaveCount(0);
      });

      test("creates a new notice and increments the active count, showing a success toast", async ({
        page,
      }) => {
        await expect(page.getByText(`${activeNoticeCount} active`).first()).toBeVisible();

        const message = "Scheduled QPU maintenance tonight 22:00–02:00 UTC. Queue paused.";
        await page.locator("textarea#notice-message").fill(message);
        await Promise.all([
          waitForApi(page, "POST", "/admin/notices/"),
          page.locator("button", { hasText: /^Post$/i }).click(),
        ]);
        await expect(page.getByText(/notice posted/i).first()).toBeVisible();
        await expect(page.getByText(`${activeNoticeCount + 1} active`).first()).toBeVisible();
      });

      test("deletes an active notice and decrements the active count, showing a success toast", async ({
        page,
      }) => {
        await expect(page.getByText(`${activeNoticeCount} active`).first()).toBeVisible();

        await Promise.all([
          waitForApi(page, "DELETE", "/admin/notices/"),
          page.getByLabel("Delete notice").first().click(),
        ]);
        await expect(page.getByText(/notice deleted/i).first()).toBeVisible();
        await expect(page.getByText(`${activeNoticeCount - 1} active`).first()).toBeVisible();
      });

      test("paginates through notices with Previous/Next controls", async ({ page }) => {
        const previous = page.getByLabel("Go to previous page");
        const next = page.getByLabel("Go to next page");
        await expect(previous).toHaveAttribute("aria-disabled", "true");
        await expect(next).toHaveAttribute("aria-disabled", "false");

        await Promise.all([waitForApi(page, "GET", "/admin/notices"), next.click()]);
        await expect(page.locator("[aria-current='page']")).toHaveText("2");
        await expect(previous).toHaveAttribute("aria-disabled", "false");
      });
    }
  });
}

function deviceSelector(page: Page) {
  return page.locator("[data-testid='admin-control-header'] [role='combobox']");
}

async function selectDevice(page: Page, name: string) {
  await deviceSelector(page).click();
  await page.locator("[role='option']", { hasText: name }).click();
}

function backendCard(page: Page) {
  return page.getByTestId("backend-control-card");
}

function backendToggle(page: Page) {
  return backendCard(page).locator("button[role='switch']");
}

function recordRequests(page: Page, method: string, path: RegExp): Request[] {
  const requests: Request[] = [];
  page.on("request", (request) => {
    if (request.method() === method && path.test(new URL(request.url()).pathname)) {
      requests.push(request);
    }
  });
  return requests;
}
