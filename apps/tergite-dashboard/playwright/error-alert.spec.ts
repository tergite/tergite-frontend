import { type Page } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { type User } from "../types";

const API_URL = process.env.VITE_API_BASE_URL;

// the alerts do not depend on the user
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com"].includes(v.email),
);

for (const user of users) {
  const username = user.email.split("@")[0];

  test.describe(`error-alert page for '${username}'`, () => {
    test.beforeEach(async ({ page }) => {
      const serverError = { status: 500, json: { detail: "dummy server error" } };
      await page.route(`${API_URL}/devices/*`, (route) => route.fulfill(serverError));
      await page.route(`${API_URL}/devices/loke`, (route) => route.fulfill(serverError));
    });

    test("renders on unexpected error on home screen", async ({ page, loginAs }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/"), loginAs(user, "./")]);
      await expectServerErrorAlert(page);
    });

    test("renders on unexpected error on devices screen", async ({ page, loginAs }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/"), loginAs(user, "devices")]);
      await expectServerErrorAlert(page);
    });

    test("renders on unexpected error on device-detail screen", async ({ page, loginAs }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/loke"), loginAs(user, "devices/loke")]);
      await expectServerErrorAlert(page);
    });
  });
}

async function expectServerErrorAlert(page: Page) {
  await expect(page.getByText("500").first()).toBeVisible();
  await expect(page.getByText("dummy server error").first()).toBeVisible();
  await page.locator("button", { hasText: /back/i }).first().click();
}
