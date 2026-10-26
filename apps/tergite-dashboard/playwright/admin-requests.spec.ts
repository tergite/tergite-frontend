import type { Page } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { innermost } from "./utils/locators";
import { getUserRequestDetails } from "../src/lib/user-requests";
import {
  type Project,
  type User,
  type UserRequest,
  UserRequestStatus,
  UserRequestType,
  UserRole,
} from "../dev/mock-api/types";

const projects = readFixture<Project[]>("projects");
const projectsIndex = Object.fromEntries(projects.map((v, i) => [v.id, i]));
const userRequests = readFixture<UserRequest[]>("user-requests");
// the admin, and a user the page is forbidden to
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "john.doe@example.com"].includes(v.email),
);

const requestsTableHeaders = ["Title", "Type", "Requested by", "Created", "Status", ""];
// '1 day ago' or '2 days 2 hours ago'
const createdCellText =
  /\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i;
const relativeTime =
  /(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+( ago)?/i;

for (const user of users) {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = user.email.split("@")[0];
  // the page lists the pending requests awaiting this user's decision, newest first
  const pendingUserRequests = userRequests
    .filter((v) => v.status === UserRequestStatus.PENDING && v.target_user_ids.includes(user.id))
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const qpuTimeRequests = pendingUserRequests.filter(
    (v) => v.type === UserRequestType.PROJECT_QPU_SECONDS,
  );

  test.describe(`admin user requests page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        isAdmin && waitForApi(page, "GET", "/me/requests/"),
        loginAs(user, "admin-requests"),
      ]);
    });

    if (isAdmin) {
      test("renders number of pending requests", async ({ page }) => {
        await openHome(page);

        await expect(pendingCount(page, pendingUserRequests.length)).toBeAttached();
      });

      test("does not render number of pending requests when sidebar is collapsed", async ({
        page,
      }) => {
        await openHome(page);

        await page
          .locator("[data-testid='sidebar'] [aria-label='PanelLeftClose']")
          .locator("..")
          .click();

        await expect(pendingCount(page, pendingUserRequests.length)).toHaveCount(0);
      });

      test("renders the admin requests page when nav item is clicked", async ({ page }) => {
        await openHome(page);

        await page.locator("[data-testid='sidebar'] a[href='/ui/admin-requests']").click();
        await expect(page).toHaveURL("admin-requests");
      });
    } else {
      test("requests link in sidebar does not exist", async ({ page }) => {
        await openHome(page);

        await expect(page.locator("[data-testid='sidebar'] a[href='/ui/admin-requests']")).toHaveCount(
          0,
        );
      });

      test("redirects to home when admin-requests URL is visited", async ({ page }) => {
        await expect(page).toHaveURL("./");
      });
    }

    if (isAdmin) {
      test("renders all pending user requests", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const card = page.locator(".bg-card", { hasText: /pending user requests/i });
        const rows = card.locator("tbody tr");

        await expect(card.locator("thead th")).toHaveText(requestsTableHeaders);
        await expect(rows).toHaveCount(pendingUserRequests.length || 1);
        if (pendingUserRequests.length === 0) {
          await expect(rows.locator("td", { hasText: /no results/i })).toBeVisible();
        }
        for (const [idx, request] of pendingUserRequests.entries()) {
          await expect(rows.nth(idx).locator("td")).toHaveText([
            getTitle(request),
            request.type,
            `${request.requester_name}`,
            createdCellText,
            new RegExp(request.status, "i"),
            // every row here is pending, so both quick responses are offered
            /approve\s*reject/i,
          ]);
        }
      });

      test("filters the list of user requests", async ({ page }) => {
        const filterMaps = [
          {
            input: { title: "close" },
            result: pendingUserRequests.filter((v) => /close/i.test(getTitle(v))),
          },
          {
            input: { title: "test 2", type: UserRequestType.PROJECT_QPU_SECONDS },
            result: pendingUserRequests.filter(
              (v) => /test 2/i.test(getTitle(v)) && v.type == UserRequestType.PROJECT_QPU_SECONDS,
            ),
          },
          {
            input: { requester_name: "pa" },
            result: pendingUserRequests.filter((v) => /pa/i.test(v.requester_name ?? "")),
          },
          {
            input: { status: UserRequestStatus.REJECTED },
            result: pendingUserRequests.filter((v) => v.status === UserRequestStatus.REJECTED),
          },
          {
            input: { type: UserRequestType.CLOSE_PROJECT },
            result: pendingUserRequests.filter((v) => v.type === UserRequestType.CLOSE_PROJECT),
          },
          {
            input: {
              title: "test",
              requester_name: "j",
              status: UserRequestStatus.PENDING,
              type: UserRequestType.PROJECT_QPU_SECONDS,
            },
            result: pendingUserRequests.filter(
              (v) =>
                /test/i.test(getTitle(v)) &&
                v.status === UserRequestStatus.PENDING &&
                /j/i.test(v.requester_name ?? "") &&
                v.type == UserRequestType.PROJECT_QPU_SECONDS,
            ),
          },
        ];

        await page.setViewportSize({ width: 1728, height: 1117 });
        const table = page.locator(".bg-card table");
        const form = page.locator("[data-cy-filter-form]");
        await page.locator(".bg-card [aria-label='Filter']").click();

        for (const { input, result } of filterMaps) {
          if (input.title) await form.locator("input[name='title']").fill(input.title);
          if (input.requester_name) {
            await form.locator("input[name='requester_name']").fill(input.requester_name);
          }
          if (input.type) {
            await form.locator("#request-type-select").click();
            await page.locator("[data-cy-user-request-type-select]").getByText(input.type).click();
          }
          if (input.status) {
            await form.locator("#request-status-select").click();
            await page
              .locator("[data-cy-user-request-status-select]")
              .getByText(new RegExp(input.status, "i"))
              .click();
          }
          await form.locator("button[type='submit']").click();

          await expect(table.locator("tbody tr")).toHaveCount(result.length || 1);
          for (const request of result) {
            await expectTitleListed(page, getTitle(request));
          }

          await form.locator("button[type='reset']").click();

          await expect(table.locator("tbody tr")).toHaveCount(pendingUserRequests.length || 1);
          for (const request of pendingUserRequests) {
            await expectTitleListed(page, getTitle(request));
          }
        }
      });

      test("renders sidebar placeholder by default", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const placeholder = page.locator("#sidebar-placeholder");

        await expect(page.locator("#request-summary")).toHaveCount(0);
        await expect(placeholder.locator("h3", { hasText: /user request title/i })).toBeVisible();
        await expect(
          placeholder.locator(".font-semibold", { hasText: /request details/i }),
        ).toBeVisible();
        await expect(
          placeholder.locator(".text-muted-foreground", {
            hasText: /click any row to show details here/i,
          }),
        ).toBeVisible();
      });

      test("renders user request summary when row is clicked", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const rows = page.locator(".bg-card tbody tr");
        const summary = page.locator("#request-summary");
        const body = summary.locator("[data-cy-request-body]");
        const info = summary.locator("[data-cy-additional-information]");
        await expect(rows).toHaveCount(pendingUserRequests.length || 1);

        for (const [idx, request] of pendingUserRequests.entries()) {
          await rows.nth(idx).click();

          await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
          await expect(summary.locator("h3", { hasText: getTitle(request) })).toBeVisible();

          await expect(body.locator(".font-semibold", { hasText: /^request$/i })).toBeVisible();
          for (const [prop, value] of Object.entries(getUserRequestDetails(request))) {
            const label = new RegExp(prop.replace(/-|_/g, " "), "i");
            const text = Array.isArray(value) ? value.join(", ") : `${value}`;
            await expect(innermost(body, "div", label).getByText(text).first()).toBeVisible();
          }

          await expect(
            info.locator(".font-semibold", { hasText: /^additional information$/i }),
          ).toBeVisible();
          await expect(
            innermost(info, "div", /requested by/i).getByText(`${request.requester_name}`).first(),
          ).toBeVisible();
          await expect(
            innermost(info, "div", /status/i).getByText(request.status).first(),
          ).toBeVisible();
          await expect(
            innermost(info, "div", /created/i).getByText(relativeTime).first(),
          ).toBeVisible();

          await expect(summary.locator("button", { hasText: /approve/i })).toBeVisible();
          await expect(summary.locator("button", { hasText: /reject/i })).toBeVisible();
        }
      });

      test("approves straight from the row, without opening the request", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });

        const title = getTitle(qpuTimeRequests[0]);
        await page
          .locator(".bg-card tbody tr", { hasText: title })
          .locator("[data-cy-row-approve]")
          .click();

        // the table lists only pending requests, so an approved one drops out
        await expect(page.locator(".bg-card tbody td", { hasText: title })).toHaveCount(0);
        // and the row click never fired, so no detail panel opened
        await expect(page.locator("#request-summary")).toHaveCount(0);
      });

      test("approving a QPU time request increases project QPU time and removes request from pending list", async ({
        page,
      }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const qpuSeconds = Object.fromEntries(projects.map((v) => [v.id, v.qpu_seconds]));
        let pendingTotal = pendingUserRequests.length;

        for (const request of qpuTimeRequests) {
          const projectId = request.resource_id;
          const isProjectMember = projects[projectsIndex[projectId]].user_ids.includes(user.id);

          if (isProjectMember) await expectQpuSeconds(page, projectId, qpuSeconds[projectId]);

          await respondFromSummary(page, getTitle(request), /approve/i);

          pendingTotal -= 1;
          qpuSeconds[projectId] += request.metadata.seconds ?? 0;

          await expect(pendingCount(page, pendingTotal)).toBeAttached();

          // QPU seconds is incremented
          if (isProjectMember) await expectQpuSeconds(page, projectId, qpuSeconds[projectId]);
        }
      });

      test("rejecting a QPU time request removes request from pending list", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        let pendingTotal = pendingUserRequests.length;

        for (const request of qpuTimeRequests) {
          const projectId = request.resource_id;
          const project = projects[projectsIndex[projectId]];
          const isProjectMember = project.user_ids.includes(user.id);

          if (isProjectMember) await expectQpuSeconds(page, projectId, project.qpu_seconds);

          await respondFromSummary(page, getTitle(request), /reject/i);

          pendingTotal -= 1;

          await expect(pendingCount(page, pendingTotal)).toBeAttached();

          // QPU seconds is unchanged
          if (isProjectMember) await expectQpuSeconds(page, projectId, project.qpu_seconds);
        }
      });
    }
  });
}

async function openHome(page: Page) {
  await Promise.all([waitForApi(page, "GET", "/me/profile"), page.goto("./")]);
  await expect(page).toHaveURL("./");
}

function pendingCount(page: Page, count: number) {
  return page.locator("[data-testid='sidebar'] a[href='/ui/admin-requests'] .bg-primary", {
    hasText: `${count}`,
  });
}

async function expectTitleListed(page: Page, title: string) {
  await expect(
    page.locator(".bg-card table tr td:first-child", { hasText: title }).first(),
  ).toBeVisible();
}

async function expectQpuSeconds(page: Page, projectId: string, seconds: number) {
  await Promise.all([waitForApi(page, "GET", "/me/projects/"), page.goto("projects")]);
  await expect(
    page.locator(
      `.bg-card tbody tr[data-id='${projectsIndex[projectId]}'] td[data-header='qpu_seconds']`,
      { hasText: new RegExp(`${seconds} seconds`, "i") },
    ),
  ).toBeVisible();
}

async function respondFromSummary(page: Page, title: string, response: RegExp) {
  await Promise.all([waitForApi(page, "GET", "/me/requests/"), page.goto("admin-requests")]);
  const titleCell = page.locator(".bg-card tbody td", { hasText: title });
  const summary = page.locator("#request-summary");

  await page.locator(".bg-card tbody tr", { hasText: title }).click();
  await expect(summary.locator("h3", { hasText: title })).toBeVisible();
  await expect(titleCell).toBeVisible();

  await summary.locator("button", { hasText: response }).click();

  await expect(titleCell).toHaveCount(0);
  await expect(summary).toHaveCount(0);
}

function getTitle(userRequest: UserRequest): string {
  // an admin sees every project, so knows the name of the one requested on
  const project = projects[projectsIndex[userRequest.resource_id]];
  const projectName = project?.name ?? userRequest.resource_id;
  return {
    [UserRequestType.CLOSE_PROJECT]: `Close project '${projectName}'`,
    [UserRequestType.CREATE_PROJECT]: `Create new project '${userRequest.metadata.name}'`,
    [UserRequestType.PROJECT_QPU_SECONDS]: `Add QPU time on project: '${projectName}'`,
    [UserRequestType.TRANSFER_PROJECT]: `Transfer project '${projectName}'`,
    [UserRequestType.PROJECT_ACCESS]: `Join project '${projectName}'`,
  }[userRequest.type];
}
