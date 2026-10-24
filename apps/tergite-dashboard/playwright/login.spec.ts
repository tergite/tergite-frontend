import { decodeJwt } from "jose";
import { type Page } from "@playwright/test";
import { expect, readFixture, signSession, test, waitForApi } from "./fixtures";
import { type AuthProvider, type User } from "../types";

const invalidFormatEmailAddresses = ["john", "1", "john.com", "http://example.com"];

// an email domain with a provider, and one without
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "wrong.domain@domain.com"].includes(v.email),
);
const authProviders = readFixture<AuthProvider[]>("auth-providers");
const apiBaseUrl = process.env.VITE_API_BASE_URL!;

for (const user of users) {
  const [username, emailDomain] = user.email.split("@");
  const availableAuthProviders = authProviders.filter((v) => v.email_domain === emailDomain);
  const isDomainSupported = availableAuthProviders.length > 0;

  test.describe(`login page for authenticated user '${username}'`, () => {
    test.beforeEach(async ({ page, apiUrl, baseURL }) => {
      const dashboardUrl = `${baseURL}/`;
      const isFullE2E = dashboardUrl.startsWith("http://127.0.0.1:3000");
      const domain = process.env.VITE_COOKIE_DOMAIN!;
      const cookieName = process.env.VITE_COOKIE_NAME!;
      const cookieExpiry = Math.round((Date.now() + 800_000) / 1000);

      if (isFullE2E) {
        const openidAuthUrl = process.env.OPENID_AUTH_URL!;
        // stand-ins for a real OpenID Connect server
        await page.route(`${dashboardUrl}?set-cookie=true`, async (route) => {
          const token = await signSession(user, cookieExpiry);
          const cookie = `${cookieName}=${token}; Domain=${domain}; Secure; HttpOnly; SameSite=Lax; Path=/; Expires=${cookieExpiry}`;
          const response = await route.fetch();
          await route.fulfill({
            response,
            headers: { ...response.headers(), "set-cookie": cookie },
          });
        });
        await page.route(
          (url) => url.href.startsWith(openidAuthUrl),
          async (route) => {
            const state = new URL(route.request().url()).searchParams.get("state");
            const stateObj = decodeJwt(`${state}`);
            await route.fulfill({
              status: 302,
              headers: { location: `${stateObj.next}?set-cookie=true` },
            });
          },
        );
      }

      await page.context().addCookies([
        {
          name: process.env.USER_ID_COOKIE_NAME!,
          value: user.id,
          domain,
          path: "/",
          httpOnly: true,
          secure: false,
          sameSite: "Lax",
        },
      ]);

      await fetch(`${apiUrl}/refreshed-db`);

      await Promise.all([waitForApi(page, "GET", "/devices/"), page.goto("/")]);
    });

    test("renders correctly", async ({ page }) => {
      const logo = page.locator("[data-cy-logo]");
      await expect(logo).toContainText("WACQT");
      await expect(logo).toContainText("Wallenberg Centre for Quantum Technology");

      await expect(page.locator("input[name=email]")).toHaveAttribute(
        "placeholder",
        /email address:/i,
      );

      await expect(nextButton(page)).toBeVisible();
    });

    if (!isDomainSupported) {
      test(`renders 'unauthorized' error message for '${user.email}'`, async ({ page }) => {
        const error = page.locator("p.text-destructive");
        await expect(error).toHaveCount(0);

        await page.locator("input[name=email]").fill(user.email);
        await nextButton(page).click();

        await expect(error.filter({ hasText: /not found/i })).toBeVisible();
      });
    }

    if (isDomainSupported) {
      test(`redirects to the home page of the dashboard`, async ({ page, baseURL }) => {
        const dashboardUrl = `${baseURL}/`;
        const isFullE2E = dashboardUrl.startsWith("http://127.0.0.1:3000");
        await page.locator("input[name=email]").fill(user.email);
        await nextButton(page).click();

        const jobsLoaded = waitForApi(page, "GET", "/me/jobs/");
        const authorized =
          isFullE2E && page.waitForRequest((v) => v.url().startsWith(process.env.OPENID_AUTH_URL!));
        await page.locator("[data-cy-login-link]").first().click();
        let finalUrl = dashboardUrl;
        if (isFullE2E) {
          await authorized;
          finalUrl = `${dashboardUrl}?set-cookie=true`;
        }

        await jobsLoaded;

        await expect(page).toHaveURL(finalUrl);
        await expect(page.locator("nav a", { hasText: /dashboard/i }).first()).toBeVisible();
      });
    }
  });

  test.describe(`login page for unauthenticated user '${username}'`, () => {
    test.beforeEach(async ({ page }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/"), page.goto("/")]);
    });

    test("toggles dark mode", async ({ page }) => {
      const toDarkBtn = page.locator('[aria-label="Moon"]');
      const toLightBtn = page.locator('[aria-label="Sun"]');
      const darkHtml = page.locator("html.dark");
      await expect(toLightBtn).toHaveCount(0);

      await toDarkBtn.click();
      await expect(darkHtml).toBeVisible();
      await expect(toDarkBtn).toHaveCount(0);

      await expect(toLightBtn).toBeVisible();

      await toLightBtn.click();
      await expect(darkHtml).toHaveCount(0);
      await expect(toDarkBtn).toBeVisible();
      await expect(toLightBtn).toHaveCount(0);
    });

    if (isDomainSupported) {
      test(`redirects to the home page of the dashboard`, async ({ page, baseURL }) => {
        const dashboardUrl = `${baseURL}/`;
        await page.locator("input[name=email]").fill(user.email);
        await Promise.all([
          page.waitForResponse(
            (v) =>
              v.url().endsWith(`/auth/providers/?email_domain=${emailDomain}`) &&
              v.request().method() === "GET",
          ),
          nextButton(page).click(),
        ]);

        for (const provider of availableAuthProviders) {
          await expect(
            page.locator("a", { hasText: new RegExp(`login with ${provider.name}`, "i") }).first(),
          ).toHaveAttribute(
            "href",
            `${apiBaseUrl}/auth/${provider.name}/auto-authorize?next=${dashboardUrl.slice(0, -1)}`,
          );
        }
      });
    }
  });
}

for (const email of invalidFormatEmailAddresses) {
  test.describe(`login with invalid email ${email}`, () => {
    test.beforeEach(async ({ page }) => {
      await Promise.all([waitForApi(page, "GET", "/devices/"), page.goto("/")]);
    });

    test(`renders error message`, async ({ page }) => {
      const error = page.locator("p.text-destructive");
      await expect(error).toHaveCount(0);

      await page.locator("input[name=email]").fill(email);
      await nextButton(page).click();

      await expect(
        error.filter({ hasText: /invalid email; expected xxx@bxxxx.xxx/i }),
      ).toBeVisible();
    });
  });
}

function nextButton(page: Page) {
  return page.locator("button[type=submit]", { hasText: /next/i });
}

/** Signs a session JWT as the mock API's generateJwt does; importing that would load its JSON */
