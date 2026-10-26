import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { test as base, type Page } from "@playwright/test";
import { SignJWT } from "jose";
import { type User } from "../dev/mock-api/types";

// the API address the test build was made with; each worker's requests to it go to its own API,
// unless the tests run against the full stack, whose API it is
const BUILT_API_URL = process.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8002";
// set apart for each run of Playwright at once, so that their APIs do not share ports
const FIRST_API_PORT = parseInt(process.env.PW_API_PORT_BASE ?? "8100");
// dev/e2e_native_test.sh sets it to test the full stack, whose data all tests share
const IS_STACK = !!process.env.DASHBOARD_URL;

// a test that writes leaves its worker's data for the next test to reset, and one that only
// reads does not, as resetting the stack takes a second; each worker starts with a reset
let hasWritten = true;

interface TestFixtures {
  /** Resets the worker's data if a test wrote to it since the last reset */
  resetData: () => Promise<void>;
  /** Resets the worker's data as resetData does, signs the user in and opens the path */
  loginAs: (user: User, path: string) => Promise<void>;
}

interface WorkerFixtures {
  /** The URL of this worker's own mock API, whose data no other worker touches, or the stack's */
  apiUrl: string;
}

export const test = base.extend<TestFixtures, WorkerFixtures>({
  apiUrl: [
    // eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's needs from this pattern
    async ({}, use, workerInfo) => {
      if (IS_STACK) {
        await use(BUILT_API_URL);
        return;
      }
      const port = FIRST_API_PORT + workerInfo.parallelIndex;
      // detached, so that killing its process group also stops the node that tsx starts
      const api = spawn(
        "node_modules/.bin/tsx",
        ["--env-file=.env.test", "dev/mock-api/server.ts"],
        { env: { ...process.env, API_PORT: `${port}` }, detached: true, stdio: "ignore" },
      );
      const url = `http://127.0.0.1:${port}`;
      await waitUntilServing(url);
      await use(url);
      process.kill(-api.pid!);
    },
    { scope: "worker" },
  ],

  page: async ({ page, apiUrl }, use) => {
    page.on("request", (request) => {
      if (request.method() !== "GET" && request.url().startsWith(BUILT_API_URL)) {
        hasWritten = true;
      }
    });
    if (!IS_STACK) {
      // the browser follows a redirect without routing it, so one to the built API must name
      // this worker's API itself
      await page.route(`${BUILT_API_URL}/**`, async (route) => {
        const url = route.request().url().replace(BUILT_API_URL, apiUrl);
        const response = await route.fetch({ url, maxRedirects: 0 });
        const headers = response.headers();
        if (headers.location) headers.location = headers.location.replace(BUILT_API_URL, apiUrl);
        await route.fulfill({ response, headers });
      });
    }
    await use(page);
  },

  resetData: async ({ apiUrl }, use) => {
    await use(async () => {
      if (!hasWritten) return;
      hasWritten = false;
      await fetch(IS_STACK ? process.env.DB_RESET_URL! : `${apiUrl}/refreshed-db`);
    });
  },

  loginAs: async ({ page, resetData }, use) => {
    await use(async (user, path) => {
      await resetData();
      const expiry = Math.round((Date.now() + 800_000) / 1000);
      const jwt = await signSession(user, expiry);
      await page.context().addCookies([
        {
          name: process.env.VITE_COOKIE_NAME!,
          value: jwt,
          domain: process.env.VITE_COOKIE_DOMAIN!,
          path: "/",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
          expires: expiry,
        },
      ]);
      await Promise.all([waitForApi(page, "GET", "/me/profile"), page.goto(path)]);
    });
  },
});

export { expect } from "@playwright/test";

/** Reads a JSON fixture of fixtures/, which the mock API and the full-stack e2e also use */
export function readFixture<T>(name: string): T {
  const url = new URL(`../fixtures/${name}.json`, import.meta.url);
  return JSON.parse(readFileSync(url, "utf8")) as T;
}

/** Waits for the response to the first request with the method whose path starts with the given one */
export function waitForApi(page: Page, method: string, pathPrefix: string) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === method &&
      new URL(response.url()).pathname.startsWith(pathPrefix),
  );
}

/** Signs the session cookie's JWT as the mock API's generateJwt does; importing that would load its JSON */
export function signSession(user: User, expiry: number): Promise<string> {
  return new SignJWT({ sub: user.id, roles: [...user.roles] })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setAudience([process.env.AUTH_AUDIENCE!])
    .setExpirationTime(expiry)
    .sign(new TextEncoder().encode(process.env.JWT_SECRET!));
}

async function waitUntilServing(url: string): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`the mock API at ${url} did not start`);
}
