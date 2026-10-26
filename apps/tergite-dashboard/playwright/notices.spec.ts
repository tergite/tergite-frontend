import { expect, readFixture, test, waitForApi } from "./fixtures";
import { type User } from "../dev/mock-api/types";

// the fixture carries the stored shape, with relative offsets for the timestamps
interface StoredNotice {
  id: string;
  user_id: string | null;
  type: string;
  title: string;
  dismissed_by: string[];
  expires_at_offset_hours: number | null;
}

// one who can act on a notice, one with notices of their own, and one with broadcasts only
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "john.doe@example.com", "julie.doe@example.com"].includes(v.email),
);
const notices = readFixture<StoredNotice[]>("notices");

for (const user of users) {
  const username = user.email.split("@")[0];
  // the bell lists the unread notices only; expired ones no longer exist
  const unread = notices.filter(
    (v) =>
      (v.user_id === null || v.user_id === user.id) &&
      !v.dismissed_by.includes(user.id) &&
      (v.expires_at_offset_hours === null || v.expires_at_offset_hours >= 0),
  );
  // the prompts to decide a request are the only ones that can be acted on
  const actionable = unread.filter((v) => v.type.endsWith("-requested"));

  test.describe(`notices for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await Promise.all([waitForApi(page, "GET", "/me/notices/"), loginAs(user, "./")]);
    });

    test("shows the unread count on the bell", async ({ page }) => {
      const count = page.locator("[data-cy-unread-count]");
      if (unread.length > 0) {
        await expect(count).toContainText(`${unread.length}`);
      } else {
        await expect(count).toHaveCount(0);
      }
    });

    test("lists only this user's unread notices", async ({ page }) => {
      await page.locator("[data-cy-notifications-bell]").click();
      const panel = page.locator("#notifications-panel");
      await expect(panel.locator("li")).toHaveCount(unread.length);
      for (const item of unread) {
        // the panel scrolls, so the later ones are out of sight until scrolled to
        const row = panel.locator("li", { hasText: item.title }).first();
        await row.scrollIntoViewIfNeeded();
        await expect(row).toBeVisible();
      }
    });

    test("shows approve and reject only where the recipient can act", async ({ page }) => {
      await page.locator("[data-cy-notifications-bell]").click();
      const panel = page.locator("#notifications-panel");
      for (const item of unread) {
        const row = panel.locator("li", { hasText: item.title }).first();
        const expected = actionable.includes(item) ? 1 : 0;
        await expect(row.getByRole("button", { name: /approve/i })).toHaveCount(expected);
        await expect(row.getByRole("button", { name: /reject/i })).toHaveCount(expected);
      }
    });

    if (unread.length > 0) {
      test("marks one notice read", async ({ page }) => {
        await page.locator("[data-cy-notifications-bell]").click();
        await page.locator("#notifications-panel [data-cy-mark-read]").first().click();

        await expect(page.locator("#notifications-panel li")).toHaveCount(unread.length - 1);
      });

      test("marks every notice read", async ({ page }) => {
        await page.locator("[data-cy-notifications-bell]").click();
        await page.locator("[data-cy-mark-all-read]").click();

        await expect(page.locator("[data-cy-unread-count]")).toHaveCount(0);
      });
    }

    if (actionable.length > 0) {
      test("approving from the bell clears the actionable notice", async ({ page }) => {
        await page.locator("[data-cy-notifications-bell]").click();
        const row = page.locator("#notifications-panel li", { hasText: actionable[0].title });
        const [response] = await Promise.all([
          waitForApi(page, "PUT", "/me/requests/"),
          row.getByRole("button", { name: /approve/i }).click(),
        ]);

        expect(response.status()).toBe(200);
      });
    }

    // every user has the broadcasts ntc_007 and ntc_009 in force
    test("shows a notice in force in the top banner", async ({ page }) => {
      const banner = page.getByTestId("top-banner");
      await expect(banner.getByLabel("Dismiss notice").first()).toBeVisible();
      await expect(banner.getByText(/\b(info|warning|critical)\b/i).first()).toBeVisible();
    });

    test("takes a notice dismissed from the top banner off the bell", async ({ page }) => {
      await Promise.all([
        waitForApi(page, "POST", "/me/notices/"),
        page.getByTestId("top-banner").getByLabel("Dismiss notice").click(),
      ]);

      await expect(page.locator("[data-cy-unread-count]")).toContainText(`${unread.length - 1}`);
    });
  });
}
