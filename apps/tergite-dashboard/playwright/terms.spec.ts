import { expect, test } from "./fixtures";

test.describe("Loads the terms of use page", () => {
  test("should display the terms of use content", async ({ page }) => {
    await page.goto("/terms.html");
    await expect(page.getByText(/Terms of Use/).first()).toBeAttached();
  });
});
