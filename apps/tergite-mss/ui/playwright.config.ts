import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";

dotenv.config({ path: ".env.test" });

// the dashboard that MSS serves in the stack dev/e2e_native_test.sh starts
const dashboardUrl = process.env.DASHBOARD_URL;
if (!dashboardUrl) {
  throw new Error("run the e2e through dev/e2e_native_test.sh, which sets DASHBOARD_URL");
}

export default defineConfig({
  testDir: "./playwright",
  forbidOnly: !!process.env.CI,
  // the tests share the stack's data
  workers: 1,
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: dashboardUrl,
    timezoneId: "Europe/Stockholm",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // the viewport the specs and their screenshot baselines were written against
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 750 } },
    },
  ],
});
