import { expect, readFixture, test, waitForApi } from "./fixtures";
import { getUserRequestDetails } from "../src/lib/user-requests";
import type { User, UserRequest } from "./types";

const users = readFixture<User[]>("users");
const requests = readFixture<UserRequest[]>("user-requests");

// the fixture hangs almost every request off one requester; iterating users with no
// requests would only assert the empty table over and over
const requesters = users.filter((user) => requests.some((v) => v.requester_id === user.id));

for (const user of requesters) {
  const own = requests.filter((v) => v.requester_id === user.id);

  test.describe(`my requests page for ${user.id}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await page.setViewportSize({ width: 1728, height: 1000 });
      await Promise.all([waitForApi(page, "GET", "/me/requests/"), loginAs(user, "requests")]);
    });

    test("is reachable from the Access group in the sidebar", async ({ page }) => {
      await page.goto("./");
      await page.locator("[data-testid='sidebar'] a[href='/ui/requests']").click();
      await expect(page).toHaveURL(/\/requests$/);
    });

    test("lists every request this user made", async ({ page }) => {
      await expect(page.locator("tbody tr")).toHaveCount(own.length);
    });

    test("shows the placeholder until a row is picked", async ({ page }) => {
      await expect(page.locator("#sidebar-placeholder")).toBeVisible();
      await expect(page.locator("#request-summary")).toHaveCount(0);
    });

    test("shows what was asked for, and the outcome, when a row is picked", async ({ page }) => {
      // newest first, matching the API's sort
      const newest = [...own].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

      await page.locator("tbody tr").first().click();
      const summary = page.locator("#request-summary");
      await expect(summary.getByText(newest.status).first()).toBeVisible();
      for (const [key, value] of Object.entries(getUserRequestDetails(newest))) {
        const label = new RegExp(key.replace(/_/g, " "), "i");
        // DetailItem capitalises the label, so match without regard to case
        await expect(summary.getByText(label).first()).toBeAttached();
        await expect(
          summary.getByText(Array.isArray(value) ? value.join(", ") : `${value}`).first(),
        ).toBeAttached();
      }
    });

    test("offers no approve or reject controls on your own request", async ({ page }) => {
      await page.locator("tbody tr").first().click();
      await expect(page.locator("[data-cy-approve]")).toHaveCount(0);
      await expect(page.locator("[data-cy-reject]")).toHaveCount(0);
    });
  });
}
