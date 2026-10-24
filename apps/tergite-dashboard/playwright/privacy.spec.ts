import { expect, test } from "./fixtures";

test.describe("Loads the privacy policy page", () => {
  test("should display the privacy policy content", async ({ page }) => {
    await page.goto("/privacy.html");
    await expect(page.getByText(/Privacy Policy/).first()).toBeAttached();
  });
});
