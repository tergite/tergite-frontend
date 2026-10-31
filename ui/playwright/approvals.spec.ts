import { expect, readFixture, test, waitForApi } from "./fixtures";
import { UserRole, type User, type UserRequest } from "./types";

const users = readFixture<User[]>("users");
const requests = readFixture<UserRequest[]>("user-requests");

// a project admin, not a superuser, so only the requests on their own projects reach them
const approvers = users.filter(
  (user) =>
    !user.roles.includes(UserRole.ADMIN) &&
    requests.some((v) => v.target_user_ids.includes(user.id)),
);

for (const user of approvers) {
  const awaiting = requests.filter((v) => v.target_user_ids.includes(user.id));
  const pending = awaiting.filter((v) => v.status === "pending");

  test.describe(`approvals page for ${user.id}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await page.setViewportSize({ width: 1728, height: 1000 });
      await Promise.all([waitForApi(page, "GET", "/me/requests/"), loginAs(user, "approvals")]);
    });

    test("is reachable from the pending count on the projects page", async ({ page }) => {
      await page.goto("projects");
      const link = page.locator("[data-cy-approvals-link]");
      await expect(link).toContainText(`${pending.length} awaiting your approval`);
      await link.click();
      await expect(page).toHaveURL(/\/approvals$/);
    });

    test("lists every request awaiting this user", async ({ page }) => {
      await expect(page.locator("tbody tr")).toHaveCount(awaiting.length);
    });

    test("shows the placeholder until a row is picked", async ({ page }) => {
      await expect(page.locator("#sidebar-placeholder")).toBeVisible();
      await expect(page.locator("#approval-summary")).toHaveCount(0);
    });

    test("shows who asked when a row is picked", async ({ page }) => {
      await page.locator("tbody tr").first().click();
      const summary = page.locator("#approval-summary");
      await expect(summary.getByText(pending[0].requester_name!).first()).toBeVisible();
      await expect(summary.getByText("pending").first()).toBeVisible();
    });

    test("approving a request marks it approved and clears the pending count", async ({
      page,
    }) => {
      await page.locator("tbody tr").first().click();
      await Promise.all([
        waitForApi(page, "PUT", "/me/requests/"),
        page.locator("[data-cy-approve]").click(),
      ]);

      await expect(page.locator("#sidebar-placeholder")).toBeVisible();
      await expect(page.locator("tbody tr").first()).toContainText("approved");
      await page.goto("projects");
      await expect(page.locator("[data-cy-approvals-link]")).toHaveCount(0);
    });

    test("rejecting a request marks it rejected", async ({ page }) => {
      await page.locator("tbody tr").first().click();
      await Promise.all([
        waitForApi(page, "PUT", "/me/requests/"),
        page.locator("[data-cy-reject]").click(),
      ]);

      await expect(page.locator("tbody tr").first()).toContainText("rejected");
    });
  });
}
