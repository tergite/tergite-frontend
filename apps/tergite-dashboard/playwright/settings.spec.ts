import { expect, readFixture, test, waitForApi } from "./fixtures";
import { NoticeType, type User } from "../types";

// preferences behave identically for everyone, so one representative user is enough
const [user] = readFixture<User[]>("users");
// one type the recipient can act on, one that only reports an outcome
const SAMPLE_TYPES = [NoticeType.PROJECT_ACCESS_REQUESTED, NoticeType.QPU_SECONDS_GRANTED];
const PREFERENCES_PATH = "/me/notices/preferences/";

test.describe(`settings for ${user.email.split("@")[0]}`, () => {
  test.beforeEach(async ({ page, loginAs }) => {
    await Promise.all([waitForApi(page, "GET", PREFERENCES_PATH), loginAs(user, "/settings")]);
  });

  test("is reachable from the user menu", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-testid='topbar'] [aria-label='UserRound']").click({ force: true });
    await page.locator("[data-cy-settings-link]").click();

    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByText("Email notifications").first()).toBeVisible();
  });

  test("shows an email switch for every notice type", async ({ page }) => {
    const switches = page.locator("[data-cy-email-switch]");
    await expect(switches).toHaveCount(Object.values(NoticeType).length);
    for (const element of await switches.all()) {
      await expect(element).toHaveAttribute("data-state", "checked");
    }
  });

  for (const type of SAMPLE_TYPES) {
    test(`turns email off for ${type}`, async ({ page }) => {
      const emailSwitch = page.locator(`[data-cy-email-switch='${type}']`);
      await Promise.all([waitForApi(page, "PUT", PREFERENCES_PATH), emailSwitch.click()]);

      await expect(emailSwitch).toHaveAttribute("data-state", "unchecked");
    });

    test(`keeps the opt-out for ${type} after a reload`, async ({ page }) => {
      const emailSwitch = page.locator(`[data-cy-email-switch='${type}']`);
      await Promise.all([waitForApi(page, "PUT", PREFERENCES_PATH), emailSwitch.click()]);

      await Promise.all([waitForApi(page, "GET", PREFERENCES_PATH), page.reload()]);

      await expect(emailSwitch).toHaveAttribute("data-state", "unchecked");
    });
  }

  test("leaves the other types alone", async ({ page }) => {
    const [changed, untouched] = SAMPLE_TYPES;
    await Promise.all([
      waitForApi(page, "PUT", PREFERENCES_PATH),
      page.locator(`[data-cy-email-switch='${changed}']`).click(),
    ]);

    await expect(page.locator(`[data-cy-email-switch='${untouched}']`)).toHaveAttribute(
      "data-state",
      "checked",
    );
  });
});

test.describe("settings when unauthenticated", () => {
  test("redirects to login", async ({ page }) => {
    await page.goto("/settings");

    await expect(page).toHaveURL(/\/login/);
  });
});
