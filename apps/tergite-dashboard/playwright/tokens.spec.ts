import { type Locator, type Page } from "@playwright/test";
import { DateTime } from "luxon";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { checkFilters, type TableFilter } from "./utils/tables";
import { extendAppToken } from "./utils/records";
import { type AppToken, type ExtendedAppToken, type Project, type User } from "../types";

const TABLE_HEADERS = ["Title", "Project", "Expires", "Status"];
// 'in 1 day' or '2 days ago' or '+273,000 years'
const RELATIVE_TIME =
  /(in)? (\+?\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+( ago)?/i;
const PICKER_DATETIME =
  /\d+ (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Oct|Nov|Dec) \d+, \d\d:\d\d:\d\d/i;

const projects = readFixture<Project[]>("projects");
const projectsMap = Object.fromEntries(projects.map((v) => [v.id, v]));
const createdAt = new Date().toISOString();
const tokens = readFixture<(AppToken & { user_id: string })[]>("tokens").map((v) => ({
  ...v,
  created_at: createdAt,
}));
const users = readFixture<User[]>("users").filter((v) =>
  tokens.some((token) => token.user_id === v.id),
);

for (const user of users) {
  const username = user.email.split("@")[0];
  const userProjects = projects.filter((v) => v.user_ids.includes(user.id) && v.is_active);
  const allUserTokens = tokens
    .filter((v) => v.user_id === user.id && projectsMap[v.project_id])
    .map((v) => extendAppToken(v, projectsMap[v.project_id]));

  test.describe(`tokens page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await page.setViewportSize({ width: 1728, height: 1117 });
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        waitForApi(page, "GET", "/me/tokens/"),
        loginAs(user, "/tokens"),
      ]);
    });

    test("renders the tokens page when nav item is clicked", async ({ page }) => {
      await page.goto("/");
      await expect(page).toHaveURL("/");

      await page.locator("[data-testid='sidebar'] a[href='/tokens']").click();
      await expect(page).toHaveURL("/tokens");
    });

    test("renders all user's tokens with no project selected", async ({ page }) => {
      const card = page.locator(".bg-card", { hasText: /api tokens for all projects/i }).first();
      await expectTokenTable(card, allUserTokens);
    });

    test("filters the list of all tokens when no project is selected", async ({ page }) => {
      await checkFilters(
        page,
        tokenFilters(allUserTokens),
        allUserTokens.map((v) => v.title),
      );
    });

    test("renders sidebar placeholder by default with no project selected", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      await expectSidebarPlaceholder(page);
    });

    test("renders user's tokens' summary when row is clicked with no project selected", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      await expectSummaryOnRowClick(page, allUserTokens);
    });

    test("renders the list of user's tokens in selected project", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const project of userProjects) {
        await selectProject(page, project);
        const card = page
          .locator(".bg-card", { hasText: new RegExp(`api tokens for ${project.name}`, "i") })
          .first();
        await expectTokenTable(
          card,
          allUserTokens.filter((v) => v.project_id === project.id),
        );
      }
    });

    test("filters the list of tokens in given token when project is selected", async ({
      page,
    }) => {
      for (const project of userProjects) {
        await selectProject(page, project);
        const tokensForProject = allUserTokens.filter((v) => v.project_id === project.id);

        await checkFilters(
          page,
          tokenFilters(tokensForProject),
          tokensForProject.map((v) => v.title),
        );
      }
    });

    test("renders sidebar placeholder by default with project selected", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const project of userProjects) {
        await selectProject(page, project);
        await expectSidebarPlaceholder(page);
        await page.reload();
      }
    });

    test("renders user's tokens' summary when row is clicked with project selected", async ({
      page,
    }) => {
      for (const project of userProjects) {
        await selectProject(page, project);
        await expectSummaryOnRowClick(
          page,
          allUserTokens.filter((v) => v.project_id === project.id),
        );
      }
    });

    test("hides user's tokens' summary when project is changed", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const project of userProjects) {
        await selectProject(page, project);
        await expect(page.locator("#token-summary")).toHaveCount(0);

        if (allUserTokens.some((v) => v.project_id === project.id)) {
          await page.locator(".bg-card tbody tr").first().click();
          await expect(page.locator("#token-summary")).toBeVisible();
        }
      }
    });

    test("generation of new token appends token to list", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const newTokenButton = page.locator('[data-testid="top-banner"] [aria-label="RefreshCcw"]');

      for (const project of userProjects.slice(0, 1)) {
        await selectProject(page, project);
        const tokenName = new RegExp(`${project.id}-(\\d+)`, "i");

        await newTokenButton.click();
        const cell = page.locator("table tbody td").filter({ hasText: tokenName }).last();
        await expect(cell).toBeVisible();

        const timestamp = tokenName.exec((await cell.textContent()) ?? "")?.[1] ?? "";
        expect(parseFloat(timestamp)).toBeGreaterThan(new Date().getTime() - 200);
      }
    });

    test("deleting of token removes token from list and summary", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const token of allUserTokens) {
        await page.locator(".bg-card tbody tr", { hasText: token.title }).first().click();
        await expect(page.locator("#token-summary h3", { hasText: token.title })).toBeVisible();
        const cell = page.locator(".bg-card tbody td", { hasText: token.title });
        await expect(cell.first()).toBeVisible();

        await page.locator("#token-summary button", { hasText: /delete/i }).click();
        await page
          .locator("#delete-token-dialog button", { hasText: /I want to delete this token/i })
          .click();

        await expect(page.locator("#delete-token-dialog")).toHaveCount(0);
        await expect(cell).toHaveCount(0);
        await expect(page.locator("#token-summary")).toHaveCount(0);
      }
    });

    test("More than 10 tokens activates the pagination button on the table", async ({ page }) => {
      const newTokenButton = page.locator('[data-testid="top-banner"] [aria-label="RefreshCcw"]');
      const newPageButton = page.locator('.bg-card [aria-label="ChevronRight"]');

      for (const project of userProjects.slice(0, 1)) {
        await selectProject(page, project);
        const projectsTokens = allUserTokens.filter((v) => v.project_id === project.id);
        if (projectsTokens.length < 10) {
          await expect(newPageButton).toHaveAttribute("disabled");
        }

        for (let index = projectsTokens.length; index <= 10; index++) {
          await newTokenButton.click();
        }

        await expect(newPageButton).not.toHaveAttribute("disabled");
      }
    });

    test("editing the lifespan of the live token with no project selected updates summary and table", async ({
      page,
      timezoneId,
    }) => {
      // edits every live token in turn, so it outlasts the default timeout on a busy machine
      test.slow();
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const [index, token] of allUserTokens.entries()) {
        if (token.lifespan_seconds > 0) {
          const newExpiry = nextMonthOn23rd(timezoneId);
          await page
            .locator(`.bg-card tbody tr[data-id='${index}']`, { hasText: token.title })
            .click();

          await page.locator("#token-summary button", { hasText: /edit lifespan/i }).click();
          await pickNewExpiry(page);
          await page
            .locator("#edit-lifespan-dialog button[type='submit']", { hasText: /save/i })
            .click();

          await expectNewExpiry(page, token, index, newExpiry);
        }
      }
    });

    test("editing the lifespan of the expired token with no project selected is not allowed", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      await expectExpiredLifespansLocked(page, allUserTokens);
    });

    test("editing the lifespan of the live token with project selected updates summary and table", async ({
      page,
      timezoneId,
    }) => {
      for (const project of userProjects) {
        await selectProject(page, project);
        const tokensForProject = allUserTokens.filter((v) => v.project_id === project.id);

        for (const [index, token] of tokensForProject.entries()) {
          if (token.lifespan_seconds > 0) {
            const newExpiry = nextMonthOn23rd(timezoneId);
            await page
              .locator(`.bg-card tbody tr[data-id='${index}']`, { hasText: token.title })
              .click();

            await page.locator("#token-summary button", { hasText: /edit lifespan/i }).click();
            await pickNewExpiry(page);
            // closes the picker
            await page
              .locator("#edit-lifespan-dialog h2", { hasText: /edit lifespan of token/i })
              .click();
            await page
              .locator("#edit-lifespan-dialog button[type='submit']", { hasText: /save/i })
              .click();

            await expectNewExpiry(page, token, index, newExpiry);
          }
        }
      }
    });

    test("editing the lifespan of the expired token with project selected is not allowed", async ({
      page,
    }) => {
      for (const project of userProjects) {
        await selectProject(page, project);
        await expectExpiredLifespansLocked(
          page,
          allUserTokens.filter((v) => v.project_id === project.id),
        );
      }
    });
  });
}

function tokenFilters(tokens: ExtendedAppToken[]): TableFilter[] {
  const titles = (predicate: (token: ExtendedAppToken) => boolean) =>
    tokens.filter(predicate).map((v) => v.title);
  return [
    { inputs: { title: "work" }, expected: titles((v) => /work/i.test(v.title)) },
    {
      inputs: { title: "home" },
      status: /expired/i,
      expected: titles((v) => /home/i.test(v.title) && v.is_expired),
    },
    {
      inputs: { project_name: "est 1" },
      expected: titles((v) => /est 1/i.test(v.project_name)),
    },
    {
      inputs: { project_name: "test" },
      expected: titles((v) => /test/i.test(v.project_name)),
    },
    {
      inputs: { title: "token" },
      status: /live/i,
      expected: titles((v) => /token/i.test(v.title) && !v.is_expired),
    },
    { inputs: {}, status: /live/i, expected: titles((v) => !v.is_expired) },
    { inputs: {}, status: /expired/i, expected: titles((v) => v.is_expired) },
    {
      inputs: { title: "home", project_name: "te" },
      status: /expired/i,
      expected: titles((v) => /te/i.test(v.project_name) && v.is_expired && /home/i.test(v.title)),
    },
  ];
}

/** Selects the project and waits for its tokens, which replace the table and any filter form open on it */
async function selectProject(page: Page, project: Project) {
  await page.locator('[data-testid="topbar"] button', { hasText: /project:/i }).click();
  await Promise.all([
    page.waitForResponse((v) => v.url().endsWith(`/me/tokens/?project_id=${project.id}`)),
    page.locator('#project-selector [role="option"]', { hasText: project.name }).first().click(),
  ]);
}

async function expectTokenTable(card: Locator, tokens: ExtendedAppToken[]) {
  await expect(card.locator("thead th")).toHaveText(TABLE_HEADERS);

  const rows = card.locator("tbody tr");
  await expect(rows).toHaveCount(tokens.length || 1);
  if (tokens.length === 0) {
    await expect(rows.locator("td", { hasText: /no results/i })).toBeVisible();
  }
  for (const [index, token] of tokens.entries()) {
    await expect(rows.nth(index).locator("td")).toHaveText([
      token.title,
      token.project_name,
      RELATIVE_TIME,
      token.is_expired ? /expired/i : /live/i,
    ]);
  }
}

async function expectSidebarPlaceholder(page: Page) {
  await expect(page.locator("#token-summary")).toHaveCount(0);
  await expect(page.locator("#sidebar-placeholder h3", { hasText: /token title/i })).toBeVisible();
  await expect(
    page.locator("#sidebar-placeholder .font-semibold", { hasText: /token details/i }),
  ).toBeVisible();
  await expect(
    page.locator("#sidebar-placeholder .text-muted-foreground", {
      hasText: /click any row to show details here/i,
    }),
  ).toBeVisible();
}

async function expectSummaryOnRowClick(page: Page, tokens: ExtendedAppToken[]) {
  const rows = page.locator(".bg-card tbody tr");
  await expect(rows).toHaveCount(tokens.length || 1);

  for (const [index, token] of tokens.entries()) {
    await rows.nth(index).click();
    await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);

    const summary = page.locator("#token-summary");
    await expect(summary.locator("h3", { hasText: token.title })).toBeVisible();
    await expect(summaryItem(summary, /project/i).getByText(token.project_name)).toBeVisible();
    await expect(
      summaryItem(summary, /status/i).getByText(token.is_expired ? /expired/i : /live/i),
    ).toBeVisible();
    await expect(summaryItem(summary, /expires/i).getByText(RELATIVE_TIME)).toBeVisible();
    await expect(summaryItem(summary, /^Project/).getByText(token.project_name)).toBeVisible();
  }
}

/** The summary's line with the given label */
function summaryItem(summary: Locator, label: RegExp) {
  return summary.locator("ul > div", { hasText: label }).first();
}

/** Opens the expiry picker and sets it to the 23rd of next month at 12:00:50 */
async function pickNewExpiry(page: Page) {
  await page.locator("#edit-lifespan-dialog #datetime-input", { hasText: PICKER_DATETIME }).click();
  const picker = page.locator("[data-radix-popper-content-wrapper]");
  await picker.locator("button[name='next-month']").click();
  await picker.locator("button[name='day']:not(.opacity-50)", { hasText: "23" }).first().click();
  await picker.locator("input[type='time']").fill("12:00:50");
}

function nextMonthOn23rd(timezoneId = "UTC") {
  return DateTime.now()
    .setZone(timezoneId)
    .plus({ month: 1 })
    .set({ day: 23, hour: 12, minute: 0, second: 50 })
    .toRelative() as string;
}

async function expectNewExpiry(
  page: Page,
  token: ExtendedAppToken,
  index: number,
  newExpiry: string,
) {
  await expect(page.locator("#edit-lifespan-dialog")).toHaveCount(0);
  const summary = page.locator("#token-summary");
  await expect(summary.locator("h3", { hasText: token.title })).toBeVisible();
  await expect(summaryItem(summary, /expires/i).getByText(newExpiry)).toBeVisible();
  await expect(
    page.locator(`.bg-card tbody tr[data-id='${index}'] td[data-header='expires_at']`, {
      hasText: newExpiry,
    }),
  ).toBeVisible();
}

async function expectExpiredLifespansLocked(page: Page, tokens: ExtendedAppToken[]) {
  for (const [index, token] of tokens.entries()) {
    await page.locator(`.bg-card tbody tr[data-id='${index}']`, { hasText: token.title }).click();

    if (token.lifespan_seconds <= 0) {
      await expect(
        page.locator("#token-summary button", { hasText: /edit lifespan/i }),
      ).toBeDisabled();
    }
  }
}
