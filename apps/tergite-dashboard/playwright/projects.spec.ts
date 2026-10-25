import { type Page } from "@playwright/test";
import { Duration } from "luxon";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { checkFilters, type TableFilter } from "./utils/tables";
import {
  type Project,
  type User,
  type UserRequest,
  UserRequestType,
} from "../types";

const TABLE_HEADERS = ["Name", "ID", "Status", "Available QPU time", "Requests"];
// '1 day' or '2 days 2 hours'
const DURATION =
  /(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+/i;
const RELATIVE_TIME =
  /(in)? (\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+( ago)?/i;

const projects = readFixture<Project[]>("projects");
const qpuTimeRequestsProjectsMap = Object.fromEntries(
  readFixture<UserRequest[]>("user-requests")
    .filter((v) => v.type === UserRequestType.PROJECT_QPU_SECONDS)
    .map((v) => [v.resource_id, v]),
);
const userIds = readFixture<{ user_id: string }[]>("tokens").map((v) => v.user_id);
const allUsers = readFixture<User[]>("users");
const users = allUsers.filter((v) => userIds.includes(v.id));

for (const user of users) {
  const username = user.email.split("@")[0];
  const userProjects = projects.filter((v) => v.user_ids.includes(user.id));

  test.describe(`normal user projects page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        loginAs(user, "projects"),
      ]);
    });

    test("renders the projects page when nav item is clicked", async ({ page }) => {
      await Promise.all([waitForApi(page, "GET", "/me/profile"), page.goto("./")]);
      await expect(page).toHaveURL("./");

      await page.locator("[data-testid='sidebar'] a[href='/ui/projects']").click();
      await expect(page).toHaveURL("projects");
    });

    test("renders all user's projects", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const card = page.locator(".bg-card", { hasText: /projects/i }).first();
      await expect(card.locator("thead th")).toHaveText(TABLE_HEADERS);

      const rows = card.locator("tbody tr");
      await expect(rows).toHaveCount(userProjects.length || 1);
      if (userProjects.length === 0) {
        await expect(rows.locator("td", { hasText: /no results/i })).toBeVisible();
      }
      for (const [index, project] of userProjects.entries()) {
        const cells = rows.nth(index).locator("td");
        await expect(cells).toHaveCount(TABLE_HEADERS.length);
        await expect(cells.nth(0)).toHaveText(project.name);
        await expect(cells.nth(1)).toHaveText(project.id);
        await expect(cells.nth(2)).toHaveText(project.is_active ? /live/i : /expired/i);
        await expect(cells.nth(3)).toHaveText(DURATION);

        const requests = cells.nth(4);
        const request = qpuTimeRequestsProjectsMap[project.id];
        if (project.admin_id !== user.id) {
          await expect(requests.locator("div", { hasText: /n\/a/i }).first()).toBeVisible();
        } else if (request?.status === "pending") {
          await expect(requests.locator("button", { hasText: /request pending/i })).toBeDisabled();
          // the button carries what was asked for, so the requester does not have to go looking
          const asked = Duration.fromObject({ seconds: request.metadata.seconds }).toHuman();
          await expect(requests.locator("button", { hasText: asked })).toBeVisible();
        } else {
          await expect(requests.locator("button", { hasText: /more qpu time/i })).toBeEnabled();
        }
      }
    });

    test("filters the list of projects", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const names = (predicate: (project: Project) => boolean) =>
        userProjects.filter(predicate).map((v) => v.name);
      const filters: TableFilter[] = [
        { inputs: { name: "ate" }, expected: names((v) => /ate/i.test(v.name)) },
        {
          inputs: { name: "te" },
          status: /live/i,
          expected: names((v) => /te/i.test(v.name) && v.is_active),
        },
        { inputs: { id: "653a81b2" }, expected: names((v) => /653a81b2/i.test(v.id)) },
        {
          inputs: { name: "te" },
          status: /expired/i,
          expected: names((v) => /te/i.test(v.name) && !v.is_active),
        },
        { inputs: {}, status: /expired/i, expected: names((v) => !v.is_active) },
        { inputs: {}, status: /live/i, expected: names((v) => v.is_active) },
        {
          inputs: { name: "te", id: "653a8f19" },
          status: /live/i,
          expected: names((v) => /te/i.test(v.name) && v.is_active && /653a8f19/i.test(v.id)),
        },
      ];

      await checkFilters(page, filters, names(() => true));
    });

    test("renders sidebar placeholder by default", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      await expect(page.locator("#project-summary")).toHaveCount(0);
      await expect(
        page.locator("#sidebar-placeholder h3", { hasText: /project title/i }),
      ).toBeVisible();
      await expect(
        page.locator("#sidebar-placeholder .font-semibold", { hasText: /project details/i }),
      ).toBeVisible();
      await expect(
        page.locator("#sidebar-placeholder .text-muted-foreground", {
          hasText: /click any row to show details here/i,
        }),
      ).toBeVisible();
    });

    test("renders user's project' summary when row is clicked", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const rows = page.locator(".bg-card tbody tr");
      await expect(rows).toHaveCount(userProjects.length || 1);

      for (const [index, project] of userProjects.entries()) {
        await rows.nth(index).click();
        await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);

        await expect(page.locator("#project-summary h3", { hasText: project.name })).toBeVisible();
        await expect(summaryItem(page, /^ID/).getByText(project.id)).toBeVisible();
        await expect(
          summaryItem(page, /status/i).getByText(project.is_active ? /live/i : /expired/i),
        ).toBeVisible();
        await expect(summaryItem(page, /available qpu time/i).getByText(DURATION)).toBeVisible();
        await expect(summaryItem(page, /created at/i).getByText(RELATIVE_TIME)).toBeVisible();

        // only admins of the project can delete it
        const deleteButton = page.locator("#project-summary button", { hasText: /delete/i });
        if (project.admin_id === user.id) {
          await expect(deleteButton).toBeVisible();
        } else {
          await expect(deleteButton).toHaveCount(0);
        }
      }
    });

    test("deleting of project by admin of project removes project from list and summary", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const project of userProjects) {
        await page.locator(".bg-card tbody tr", { hasText: project.name }).first().click();
        await expect(page.locator("#project-summary h3", { hasText: project.name })).toBeVisible();
        const cell = page.locator(".bg-card tbody td", { hasText: project.name });
        await expect(cell.first()).toBeVisible();

        if (project.admin_id === user.id) {
          await page.locator("#project-summary button", { hasText: /delete/i }).click();
          await page
            .locator("#delete-project-dialog button", {
              hasText: /I want to delete this project/i,
            })
            .click();

          await expect(page.locator("#delete-project-dialog")).toHaveCount(0);
          await expect(cell).toHaveCount(0);
          await expect(page.locator("#project-summary")).toHaveCount(0);
        }
      }
    });

    test("requesting for more QPU time for project updates the request to 'pending'", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const [index, project] of userProjects.entries()) {
        if (
          qpuTimeRequestsProjectsMap[project.id]?.status !== "pending" &&
          project.admin_id === user.id
        ) {
          const row = page.locator(`.bg-card tbody tr[data-id='${index}']`);
          const requestsButton = row.locator("td[data-header='requests'] button");
          await row.filter({ hasText: project.name }).click();
          await requestsButton.filter({ hasText: /more qpu time/i }).click();

          const dialog = page.locator("#qpu-time-dialog");
          await dialog.locator("input[name='days']").fill("1");
          await dialog.locator("input[name='hours']").fill("20");
          await dialog.locator("input[name='minutes']").fill("3");
          await dialog.locator("input[name='seconds']").fill("10");
          await dialog.locator("textarea[name='reason']").fill("just some reason");
          const [response] = await Promise.all([
            waitForApi(page, "POST", "/me/requests/"),
            dialog.locator("button[type='submit']", { hasText: /submit/i }).click(),
          ]);

          await expect(dialog).toHaveCount(0);
          expect(response.request().postDataJSON().metadata.seconds).toBe(
            86_400 + 20 * 3_600 + 3 * 60 + 10,
          );
          await expect(requestsButton.filter({ hasText: /request pending/i })).toBeDisabled();
        }
      }
    });

    test("requesting for more QPU time for project that has pending qpu time requests is not allowed", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 1080, height: 750 });

      for (const [index, project] of userProjects.entries()) {
        if (
          qpuTimeRequestsProjectsMap[project.id]?.status === "pending" &&
          project.admin_id === user.id
        ) {
          await expect(
            page.locator(`.bg-card tbody tr[data-id='${index}'] td[data-header='requests'] button`, {
              hasText: /request pending/i,
            }),
          ).toBeDisabled();
        }
      }
    });
  });
}

// one who both belongs to a project and is absent from another, so every request-access branch
// is reachable without adding projects to the shared fixture
const requester = allUsers.find(
  (user) =>
    projects.some((v) => v.user_ids.includes(user.id)) &&
    projects.some((v) => !v.user_ids.includes(user.id) && v.admin_id !== user.id),
) as User;

test.describe("requesting project access", () => {
  const foreign = projects.find(
    (v) => !v.user_ids.includes(requester.id) && v.admin_id !== requester.id,
  ) as Project;

  test.beforeEach(async ({ page, loginAs }) => {
    await Promise.all([waitForApi(page, "GET", "/me/projects/"), loginAs(requester, "projects")]);
  });

  test("submits a request for a project the user is not on", async ({ page }) => {
    await page.locator("[data-cy-request-access]").click();
    const dialog = page.locator("#request-access-dialog");
    await dialog.locator("#project_id").fill(foreign.id);
    await dialog.locator("#reason").fill("joining this collaboration");
    const [response] = await Promise.all([
      waitForApi(page, "POST", "/me/requests/"),
      dialog.locator("button", { hasText: /submit/i }).click(),
    ]);

    expect(response.status()).toBe(201);
    await expect(dialog).toHaveCount(0);
    await expect(page.getByText(/access requested/i).first()).toBeVisible();
  });

  test("reports an unknown project id on the field rather than as a toast", async ({ page }) => {
    await page.locator("[data-cy-request-access]").click();
    const dialog = page.locator("#request-access-dialog");
    await dialog.locator("#project_id").fill("ffffffffffffffffffffffff");
    await dialog.locator("#reason").fill("please");
    await dialog.locator("button", { hasText: /submit/i }).click();

    await expect(
      dialog.getByText(/project ffffffffffffffffffffffff not found/i),
    ).toBeVisible();
  });

  test("refuses what cannot be a project id before asking the API", async ({ page }) => {
    const created = recordRequests(page, "POST", "/me/requests/");
    await page.locator("[data-cy-request-access]").click();
    const dialog = page.locator("#request-access-dialog");
    await dialog.locator("#project_id").fill("no-such-project-anywhere");
    await dialog.locator("#reason").fill("please");
    await dialog.locator("button", { hasText: /submit/i }).click();

    await expect(dialog.getByText(/not a project ID/i)).toBeVisible();
    expect(created.length).toBe(0);
  });
});

/** The summary's line with the given label */
function summaryItem(page: Page, label: RegExp) {
  return page.locator("#project-summary ul > div", { hasText: label }).first();
}

/** Collects the requests the page makes from now on with the method whose path starts with the given one */
function recordRequests(page: Page, method: string, pathPrefix: string) {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === method && new URL(request.url()).pathname.startsWith(pathPrefix)) {
      requests.push(request.url());
    }
  });
  return requests;
}
