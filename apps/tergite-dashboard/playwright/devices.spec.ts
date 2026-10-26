import { expect, readFixture, test, waitForApi } from "./fixtures";
import { type Device, type User } from "../dev/mock-api/types";

const LAST_ONLINE_PATTERN =
  /\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i;

// the page shows every user the same devices
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com"].includes(v.email),
);
const devices = readFixture<Device[]>("device-list");

for (const user of users) {
  const username = user.email.split("@")[0];

  test.describe(`devices list page for ${username}`, () => {
    test("renders the summaries of all devices", async ({ page, loginAs }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/"), loginAs(user, "devices")]);

      await page.setViewportSize({ width: 1080, height: 750 });
      for (const device of devices) {
        const card = page.locator(".bg-card", { hasText: device.name }).first();
        const status = device.is_online ? /online/i : /offline/i;
        const lastOnline = device.last_online ? LAST_ONLINE_PATTERN : /N\/A/i;
        const lastSeen = card.locator("div", { hasText: /last seen/i }).last();
        const qubits = card.locator("div", { hasText: /qubits/i }).last();

        await expect(card.getByText(device.name).first()).toBeVisible();
        await expect(card.getByText(status).first()).toBeVisible();
        await expect(lastSeen.getByText(lastOnline).first()).toBeVisible();
        await expect(qubits.getByText(`${device.number_of_qubits}`).first()).toBeVisible();
      }
    });

    test("renders no devices found if no devices are returned", async ({ page, loginAs }) => {
      await page.route(`${process.env.VITE_API_BASE_URL}/devices/*`, (route) =>
        route.fulfill({ json: { data: [], limit: null, skip: 0 } }),
      );
      await Promise.all([waitForApi(page, "GET", "/devices/"), loginAs(user, "devices")]);

      await page.setViewportSize({ width: 1080, height: 750 });
      await expect(page.locator("main", { hasText: /no devices found/i })).toBeAttached();
    });
  });
}
