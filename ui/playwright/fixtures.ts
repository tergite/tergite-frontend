import { readFileSync } from "node:fs";
import { test as base, type Page } from "@playwright/test";
import { SignJWT } from "jose";
import type { User } from "./types";

// the MSS the test build calls, which dev/e2e_native_test.sh starts, seeded from fixtures/
const API_URL = process.env.VITE_API_BASE_URL!;

// a test that writes leaves the data for the next test to reset, and one that only reads does
// not, as resetting the stack takes a second; the run starts with a reset
let hasWritten = true;

interface TestFixtures {
  /** Resets the stack's data if a test wrote to it since the last reset */
  resetData: () => Promise<void>;
  /** Resets the data as resetData does, signs the user in and opens the path */
  loginAs: (user: User, path: string) => Promise<void>;
}

interface WorkerFixtures {
  /** The URL of the stack's MSS */
  apiUrl: string;
}

export const test = base.extend<TestFixtures, WorkerFixtures>({
  apiUrl: [
    // eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's needs from this pattern
    async ({}, use) => use(API_URL),
    { scope: "worker" },
  ],

  page: async ({ page }, use) => {
    page.on("request", (request) => {
      if (request.method() !== "GET" && request.url().startsWith(API_URL)) {
        hasWritten = true;
      }
    });
    await use(page);
  },

  // eslint-disable-next-line no-empty-pattern -- Playwright reads a fixture's needs from this pattern
  resetData: async ({}, use) => {
    await use(async () => {
      if (!hasWritten) return;
      hasWritten = false;
      await fetch(process.env.DB_RESET_URL!);
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

/** Reads a JSON fixture of fixtures/, which the stack's databases are seeded from */
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

/** Signs the session cookie's JWT as MSS signs its own, with the stack's secret */
export function signSession(user: User, expiry: number): Promise<string> {
  return new SignJWT({ sub: user.id, roles: [...user.roles] })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setAudience([process.env.AUTH_AUDIENCE!])
    .setExpirationTime(expiry)
    .sign(new TextEncoder().encode(process.env.JWT_SECRET!));
}
