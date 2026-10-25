import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";

dotenv.config({ path: ".env.test" });

// dev/e2e_native_test.sh sets it to test the full stack, whose data all tests share
const stackDashboardUrl = process.env.DASHBOARD_URL;

export default defineConfig({
  testDir: "./playwright",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  workers: stackDashboardUrl ? 1 : undefined,
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  // apart per API port base, so that runs at the same time keep their own traces
  outputDir: `test-results/${process.env.PW_API_PORT_BASE ?? "8100"}`,
  use: {
    baseURL: stackDashboardUrl ?? "http://127.0.0.1:5173/ui/",
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
  // one build and one server for every worker; each worker brings its own mock API
  webServer: stackDashboardUrl ? undefined : {
    command:
      "npm run build -- --mode test && npm run preview -- --host 127.0.0.1 --port 5173 --strictPort",
    url: "http://127.0.0.1:5173/ui/",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
