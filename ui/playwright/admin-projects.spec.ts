import type { Locator, Page } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { innermost } from "./utils/locators";
import {
  type AdminProject,
  type Project,
  type User,
  UserRole,
} from "./types";

// Pick, not Omit: AdminProject's index signature would leave Omit with unknown values
type ProjectFormData = Pick<
  AdminProject,
  | "name"
  | "description"
  | "is_active"
  | "is_pulse_allowed"
  | "qpu_seconds"
  | "user_emails"
  | "created_at"
  | "updated_at"
>;

const userList = readFixture<User[]>("users");
// the admin, and a user the page is forbidden to
const users = userList.filter((v) =>
  ["jane.doe@example.com", "john.doe@example.com"].includes(v.email),
);
const userIdEmailMap = Object.fromEntries(userList.map((v) => [v.id, v.email]));
const projects = readFixture<Project[]>("projects").map((v) => ({
  ...v,
  admin_email: userIdEmailMap[v.admin_id],
  user_emails: v.user_ids.map((id) => userIdEmailMap[id]),
  description: v.description ?? "",
})) as AdminProject[];

const projectsTableHeaders = ["Name", "Admin", "QPU seconds", "Pulse-level", "Status"];
const relativeTime =
  /(\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+( ago)?/i;
const secondsAgo = /\d+ (seconds?)( ago)?/i;

for (const user of users) {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = user.email.split("@")[0];

  test.describe(`admin projects page for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        isAdmin && waitForApi(page, "GET", "/admin/projects/"),
        // the notice banner shows on admin screens too; letting it land keeps it from
        // shifting the layout under a click
        waitForApi(page, "GET", "/me/notices/"),
        waitForApi(page, "GET", "/counts/notices"),
        loginAs(user, "admin-projects"),
      ]);
    });

    if (isAdmin) {
      test("renders the admin projects page when nav item is clicked", async ({ page }) => {
        await openHome(page);

        await page.locator("[data-testid='sidebar'] a[href='/ui/admin-projects']").click();
        await expect(page).toHaveURL("admin-projects");
      });
    } else {
      test("admin projects link in sidebar does not exist", async ({ page }) => {
        await openHome(page);

        await expect(page.locator("[data-testid='sidebar'] a[href='/ui/admin-projects']")).toHaveCount(
          0,
        );
      });

      test("redirects to home when admin-projects URL is visited", async ({ page }) => {
        await expect(page).toHaveURL("./");
      });
    }

    if (isAdmin) {
      test("renders all projects", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const table = page.locator("#projects-table", { hasText: /projects/i });
        const rows = table.locator("tbody tr");

        await expect(table.locator("thead th")).toHaveText(projectsTableHeaders);
        await expect(rows).toHaveCount(projects.length || 1);
        if (projects.length === 0) {
          await expect(rows.locator("td", { hasText: /no results/i })).toBeVisible();
        }
        for (const [idx, project] of projects.entries()) {
          await expect(rows.nth(idx).locator("td")).toHaveText([
            project.name,
            project.admin_email,
            `${project.qpu_seconds}`,
            project.is_pulse_allowed ? "Allowed" : "",
            project.is_active ? /live/i : /expired/i,
          ]);
        }
      });

      test("filters the list of projects", async ({ page }) => {
        const filterMaps = [
          {
            input: { name: "ate" },
            result: projects.filter((v) => /ate/i.test(v.name)),
          },
          {
            input: { name: "te", is_active: true },
            result: projects.filter((v) => /te/i.test(v.name) && v.is_active),
          },
          {
            input: { admin_email: "da" },
            result: projects.filter((v) => /da/i.test(v.admin_email)),
          },
          {
            input: { name: "te", is_active: false, admin_email: undefined },
            result: projects.filter((v) => /te/i.test(v.name) && !v.is_active),
          },
          {
            input: { is_active: false },
            result: projects.filter((v) => !v.is_active),
          },
          {
            input: { is_active: true },
            result: projects.filter((v) => v.is_active),
          },
          {
            input: { name: "te", is_active: true, admin_email: "ja" },
            result: projects.filter(
              (v) => /te/i.test(v.name) && v.is_active && /ja/i.test(v.admin_email),
            ),
          },
        ];

        await page.setViewportSize({ width: 1080, height: 750 });
        const rows = page.locator("#projects-table table tbody tr");
        const form = page.locator("[data-cy-filter-form]");
        await page.locator("#projects-table [aria-label='Filter']").click();

        for (const { input, result } of filterMaps) {
          if (input.name) await form.locator("input[name='name']").fill(input.name);
          if (input.admin_email) {
            await form.locator("input[name='admin_email']").fill(input.admin_email);
          }
          if (input.is_active !== undefined) {
            await form.locator("button[role='combobox']").click();
            await page
              .locator("[data-cy-project-status-select]")
              .getByText(input.is_active ? /live/i : /expired/i)
              .click();
          }
          await form.locator("button[type='submit']").click();

          await expect(rows).toHaveCount(result.length || 1);
          for (const project of result) {
            await expectNameListed(page, project.name);
          }

          await form.locator("button[type='reset']").click();

          await expect(rows).toHaveCount(projects.length || 1);
          for (const project of projects) {
            await expectNameListed(page, project.name);
          }
        }
      });

      test("renders sidebar placeholder by default", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const placeholder = page.locator("#sidebar-placeholder");

        await expect(page.locator("#project-summary")).toHaveCount(0);
        await expect(placeholder.locator("h3", { hasText: /project title/i })).toBeVisible();
        await expect(
          placeholder.locator(".font-semibold", { hasText: /project details/i }),
        ).toBeVisible();
        await expect(
          placeholder.locator(".text-muted-foreground", {
            hasText: /click any row to show details here or click 'new' to create a project/i,
          }),
        ).toBeVisible();
      });

      test("renders project summary when row is clicked", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const rows = page.locator("#projects-table tbody tr");
        await expect(rows).toHaveCount(projects.length || 1);

        for (const [idx, project] of projects.entries()) {
          await rows.nth(idx).click();

          await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
          await expectSummaryOf(page, project);
        }
      });

      test("editing project details updates the details of the project in the table and in the summary", async ({
        page,
      }) => {
        const testData: Partial<AdminProject>[] = [
          {
            admin_email: "david.doe@example.com",
            user_emails: undefined,
            is_active: true,
            name: "fooo bar",
            description: "fancy description",
            qpu_seconds: 36_000,
          },
          {
            admin_email: undefined,
            user_emails: ["tom.doe@example.com", "jane.doe@example.com"],
            is_active: false,
            name: "fenecansi owenyini",
            description: "Musa yateeza amajju",
            qpu_seconds: 340_000_000,
          },
          {
            admin_email: "john.doe@example.com",
            user_emails: ["paul.doe@example.com"],
            is_active: true,
            name: undefined,
            description: "Bulyomu akajunwa hwabwembazi za Ruhanga",
            qpu_seconds: undefined,
          },
          {
            admin_email: "new.user@xample.com",
            user_emails: [],
            is_active: false,
            name: "Mukama ahaisibwe",
            description: undefined,
            qpu_seconds: 1_000,
          },
        ];

        await page.setViewportSize({ width: 1080, height: 750 });
        const summary = page.locator("#project-summary");
        const nameInput = innermost(summary, "div", /name/i).locator("input");
        await expect(page.locator("#projects-table tbody tr")).toHaveCount(projects.length || 1);

        for (const [idx, project] of projects.entries()) {
          const updates = testData[idx % 4];
          const expected = Object.fromEntries(
            Object.entries(project).map(([k, v]) => [k, updates[k as keyof AdminProject] ?? v]),
          ) as AdminProject;
          expected.user_emails = [...new Set([...expected.user_emails, expected.admin_email])];

          await page.locator(`#projects-table tbody tr[data-id='${idx}']`).click();

          await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();
          // the form takes the picked project's values an effect later; typing before then is lost
          await expect(nameInput).toHaveValue(project.name);

          if (updates.name) await nameInput.fill(updates.name);
          await expect(innermost(summary, "div", /^ID/).getByText(project.id)).toBeVisible();
          if (updates.description) {
            await innermost(summary, "div", /description/i)
              .locator("textarea")
              .fill(updates.description);
          }
          if (updates.is_active != undefined && project.is_active !== updates.is_active) {
            await innermost(summary, "div", /live/i).locator('button[role="switch"]').click();
          }
          if (updates.qpu_seconds != undefined) {
            await innermost(summary, "div", /qpu seconds/i)
              .locator("input")
              .fill(`${updates.qpu_seconds}`);
          }
          if (updates.admin_email) {
            await innermost(summary, "div", /admin/i).locator("input").fill(updates.admin_email);
          }
          if (updates.user_emails != undefined) {
            const members = innermost(summary, "div", /member emails/i);
            for (let i = project.user_emails.length - 1; i >= 0; i--) {
              await members.locator(`#user_emails-${i}-del-btn[aria-label="X"]`).click();
            }
            for (const [i, newEmail] of updates.user_emails.entries()) {
              await members.locator('button[aria-label="Plus"]').click();
              await members.locator(`#user_emails-${i}`).fill(newEmail);
            }
          }

          await summary.locator("button", { hasText: /update/i }).click();

          await expect(summary.locator("h3", { hasText: expected.name })).toBeVisible();
          await expect(nameInput).toHaveValue(expected.name);
          await expect(innermost(summary, "div", /^ID/).getByText(project.id)).toBeVisible();
          await expect(
            innermost(summary, "div", /description/i).locator("textarea"),
          ).toContainText(expected.description!);
          await expectEditableFields(summary, expected);
          await expect(
            innermost(summary, "div", /created/i).getByText(relativeTime).first(),
          ).toBeVisible();
          await expect(
            innermost(summary, "div", /last updated/i).getByText(secondsAgo).first(),
          ).toBeVisible();
          await expect(summary.locator("button", { hasText: /delete/i })).toBeVisible();
          await expect(summary.locator("button", { hasText: /update/i })).toBeDisabled();

          const row = page.locator(`#projects-table tbody tr[data-id='${idx}']`);
          await expect(
            row.locator("td[data-header='name']", { hasText: expected.name }),
          ).toBeVisible();
          await expect(
            row.locator("td[data-header='admin_email']", { hasText: expected.admin_email }),
          ).toBeVisible();
          await expect(
            row.locator("td[data-header='qpu_seconds']", { hasText: `${expected.qpu_seconds}` }),
          ).toBeVisible();
          await expect(row.locator("td[data-header='is_pulse_allowed']")).toHaveText(
            expected.is_pulse_allowed ? "Allowed" : "",
          );
          await expect(
            row.locator("td[data-header='is_active']", {
              hasText: expected.is_active ? /live/i : /expired/i,
            }),
          ).toBeVisible();
        }
      });

      test("creating new project adds the project in the table, the top bar", async ({ page }) => {
        const initialRowCount = projects.length;
        const today = await page.evaluate(() => new Date().toLocaleDateString());
        const now = new Date();
        const defaultValues: ProjectFormData = {
          name: `${today} project`,
          description: `Project created on ${today}`,
          is_active: true,
          is_pulse_allowed: false,
          qpu_seconds: 0,
          user_emails: [],
          created_at: now.toISOString(),
          updated_at: now.toISOString(),
        };
        const testData: Partial<AdminProject>[] = [
          {
            admin_email: "david.doe@example.com",
            user_emails: undefined,
            is_active: true,
            name: "fooo bar",
            description: "fancy description",
            qpu_seconds: 36_000,
          },
          {
            admin_email: "david.doe@example.com",
            user_emails: ["tom.doe@example.com", "jane.doe@example.com"],
            is_active: true,
            name: "fenecansi owenyini",
            description: "Musa yateeza amajju",
            qpu_seconds: 340_000_000,
          },
          {
            admin_email: "john.doe@example.com",
            user_emails: ["paul.doe@example.com"],
            is_active: true,
            name: undefined,
            description: "Bulyomu akajunwa hwabwembazi za Ruhanga",
            qpu_seconds: undefined,
          },
          {
            admin_email: "new.user@xample.com",
            user_emails: [],
            is_active: true,
            name: "Mukama ahaisibwe",
            description: undefined,
            qpu_seconds: 1_000,
          },
        ];

        await page.setViewportSize({ width: 1728, height: 1117 });
        const form = page.locator("#create-project");
        const summary = page.locator("#project-summary");

        for (const [idx, project] of testData.entries()) {
          const expected = Object.fromEntries(
            Object.entries(project).map(([k, v]) => [
              k,
              v ?? defaultValues[k as keyof ProjectFormData],
            ]),
          ) as ProjectFormData & { admin_email: string };
          expected.user_emails = [...new Set([...expected.user_emails, expected.admin_email])];
          const isListedInTopBar = expected.user_emails.includes(user.email) && expected.is_active;

          await page.locator("#projects-table button", { hasText: /new/i }).click();

          await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
          await expect(form.locator("h3", { hasText: /new project/i })).toBeVisible();

          // the email fields complete from the directory, so a superuser does
          // not have to remember an exact address
          await form.locator("input#admin_email").fill("doe");
          const suggestion = page.locator("[data-cy-suggestions] [role='option']").first();
          await expect(suggestion).toBeVisible();
          const suggested = await suggestion.innerText();
          await suggestion.click();
          await expect(form.locator("input#admin_email")).toHaveValue(suggested);

          if (project.name) {
            await innermost(form, "div", /name/i).locator("input").fill(project.name);
          }
          if (project.description) {
            await innermost(form, "div", /description/i)
              .locator("textarea")
              .fill(project.description);
          }
          await expect(
            innermost(form, "div", /live/i).locator('button[role="switch"]'),
          ).toBeDisabled();
          if (project.qpu_seconds != undefined) {
            await innermost(form, "div", /qpu seconds/i)
              .locator("input")
              .fill(`${project.qpu_seconds}`);
          }
          if (project.admin_email) {
            await innermost(form, "div", /admin/i).locator("input").fill(project.admin_email);
          }
          if (project.user_emails != undefined) {
            const members = innermost(form, "div", /member emails/i);
            for (const [i, newEmail] of project.user_emails.entries()) {
              await members.locator('button[aria-label="Plus"]').click();
              await members.locator(`#user_emails-${i}`).fill(newEmail);
            }
          }

          const topBarRefresh = isListedInTopBar && waitForApi(page, "GET", "/me/projects/");
          await form.locator("button", { hasText: /submit/i }).click();

          const row = page.locator(`#projects-table tbody tr[data-id='${initialRowCount + idx}']`);
          await expect(
            row.locator("td[data-header='name']", { hasText: expected.name }),
          ).toBeVisible();
          await expect(
            row.locator("td[data-header='admin_email']", { hasText: expected.admin_email }),
          ).toBeVisible();
          await expect(
            row.locator("td[data-header='qpu_seconds']", { hasText: `${expected.qpu_seconds}` }),
          ).toBeVisible();
          await expect(
            row.locator("td[data-header='is_active']", {
              hasText: expected.is_active ? /live/i : /expired/i,
            }),
          ).toBeVisible();

          if (topBarRefresh) {
            await topBarRefresh;
            // the projects drop down in the top bar should be updated if user is project member
            await page.locator('[data-testid="topbar"] button', { hasText: /project:/i }).click();
            await expect(
              page.locator('#project-selector [role="option"]', { hasText: expected.name }),
            ).toBeVisible();
            await page.locator('#project-selector [role="option"]', { hasText: /none/i }).click();
          }

          await expect(summary).toHaveCount(0);
          await expect(form).toHaveCount(0);
          await expect(page.locator("#sidebar-placeholder")).toBeVisible();

          await row.click();

          await expect(
            summary.locator("h3", { hasText: new RegExp(project.name as string, "i") }),
          ).toBeVisible();
          await expect(innermost(summary, "div", /name/i).locator("input")).toHaveAttribute(
            "value",
            project.name !== undefined ? new RegExp(project.name) : /\d+ project/i,
          );
          // the id is given by the API, so only that there is one is known
          await expect(innermost(summary, "div", /^ID/).getByText(/\w+/).first()).toBeVisible();
          await expect(
            innermost(summary, "div", /description/i).locator("textarea", {
              hasText: project.description ?? /project created on \d+/i,
            }),
          ).toBeVisible();
          await expectEditableFields(summary, expected);
          await expect(
            innermost(summary, "div", /Created/).getByText(secondsAgo).first(),
          ).toBeVisible();
          await expect(
            innermost(summary, "div", /Last updated/).getByText(secondsAgo).first(),
          ).toBeVisible();
          await expect(summary.locator("button", { hasText: /delete/i })).toBeEnabled();
          await expect(summary.locator("button", { hasText: /update/i })).toBeDisabled();

          await page.reload();
        }
      });

      test("cancelling project creation goes back to the default placeholder", async ({ page }) => {
        await page.setViewportSize({ width: 1728, height: 1117 });
        await page.locator("#projects-table button", { hasText: /new/i }).click();

        await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
        await page.locator("#create-project button", { hasText: /cancel/i }).click();

        await expect(page.locator("#sidebar-placeholder")).toBeVisible();
        await expect(page.locator("#create-project")).toHaveCount(0);
      });

      test("clicking x on the create project card header goes back to the default holder", async ({
        page,
      }) => {
        await page.setViewportSize({ width: 1728, height: 1117 });
        await page.locator("#projects-table button", { hasText: /new/i }).click();

        await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
        await innermost(page.locator("#create-project"), "div.justify-between", /new project/i)
          .locator("button[aria-label='X']")
          .click();

        await expect(page.locator("#sidebar-placeholder")).toBeVisible();
        await expect(page.locator("#create-project")).toHaveCount(0);
      });

      test("clicking x on the edit project card header goes back to the default", async ({
        page,
      }) => {
        await page.setViewportSize({ width: 1728, height: 1117 });
        const summary = page.locator("#project-summary");
        await expect(page.locator("#projects-table tbody tr")).toHaveCount(projects.length || 1);

        for (const [idx, project] of projects.entries()) {
          await page.locator(`#projects-table tbody tr[data-id='${idx}']`).click();

          await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();

          await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);
          await innermost(summary, "div.justify-between", new RegExp(project.name))
            .locator("button[aria-label='X']")
            .click();

          await expect(page.locator("#sidebar-placeholder")).toBeVisible();
          await expect(summary).toHaveCount(0);
        }
      });

      test("clicking a table row, when create-project form is open, opens the project for editing", async ({
        page,
      }) => {
        await page.setViewportSize({ width: 1728, height: 1117 });
        await expect(page.locator("#projects-table tbody tr")).toHaveCount(projects.length || 1);

        for (const [idx, project] of projects.entries()) {
          await page.locator("#projects-table button", { hasText: /new/i }).click();
          await expect(page.locator("#create-project")).toBeVisible();
          await expect(page.locator("#project-summary")).toHaveCount(0);
          await expect(page.locator("#sidebar-placeholder")).toHaveCount(0);

          await page.locator(`#projects-table tbody tr[data-id='${idx}']`).click();

          await expectSummaryOf(page, project);
        }
      });

      test("deleting of project removes project from list, summary and top bar", async ({
        page,
      }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const summary = page.locator("#project-summary");

        for (const project of projects) {
          const isMember = project.user_ids.includes(user.id);
          await page.locator("#projects-table tbody tr", { hasText: project.name }).click();
          await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();
          if (isMember) await expectInTopBar(page, project.name, true);

          await summary.locator("button", { hasText: /delete/i }).click();
          await page.locator("#confirm-dialog button", { hasText: /confirm/i }).click();

          await expect(page.locator("#confirm-dialog")).toHaveCount(0);
          await expect(
            page.locator("#projects-table tbody td", { hasText: project.name }),
          ).toHaveCount(0);
          await expect(summary).toHaveCount(0);
          if (isMember) await expectInTopBar(page, project.name, false);
        }
      });

      test("a project picked while the list refreshes after a deletion stays picked", async ({
        page,
      }) => {
        const [deleted, picked] = projects.slice(-2);
        await page.setViewportSize({ width: 1080, height: 750 });
        await page.route(
          (url) => url.pathname === "/me/projects/" && url.searchParams.get("is_active") === "true",
          async (route) => {
            await new Promise((resolve) => setTimeout(resolve, 2000));
            await route.fallback();
          },
        );

        await page.locator("#projects-table tbody tr", { hasText: deleted.name }).click();
        await page.locator("#project-summary button", { hasText: /delete/i }).click();
        await page.locator("#confirm-dialog button", { hasText: /confirm/i }).click();
        await expect(
          page.locator("#projects-table tbody td", { hasText: deleted.name }),
        ).toHaveCount(0);
        await page.locator("#projects-table tbody tr", { hasText: picked.name }).click();

        // the toast comes once the deletion handler has finished
        await expect(page.getByText(`Project ${deleted.name} deleted`).first()).toBeVisible();
        await expect(page.locator("#project-summary h3", { hasText: picked.name })).toBeVisible();
      });

      test("cancelling deletion of project does nothing", async ({ page }) => {
        await page.setViewportSize({ width: 1080, height: 750 });
        const summary = page.locator("#project-summary");

        for (const project of projects) {
          await page.locator("#projects-table tbody tr", { hasText: project.name }).click();
          await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();

          await summary.locator("button", { hasText: /delete/i }).click();
          await page.locator("#confirm-dialog button", { hasText: /cancel/i }).click();

          await expect(page.locator("#confirm-dialog")).toHaveCount(0);
          await expect(
            page.locator("#projects-table tbody td", { hasText: project.name }),
          ).toBeVisible();
          await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();
          if (project.user_ids.includes(user.id)) await expectInTopBar(page, project.name, true);
        }
      });
    }
  });
}

async function openHome(page: Page) {
  await Promise.all([waitForApi(page, "GET", "/me/profile"), page.goto("./")]);
  await expect(page).toHaveURL("./");
}

async function expectNameListed(page: Page, name: string) {
  await expect(
    page.locator("#projects-table table tr td:first-child", { hasText: name }).first(),
  ).toBeVisible();
}

async function expectSummaryOf(page: Page, project: AdminProject) {
  const summary = page.locator("#project-summary");

  await expect(summary.locator("h3", { hasText: project.name })).toBeVisible();
  await expect(innermost(summary, "div", /name/i).locator("input")).toHaveValue(project.name);
  await expect(innermost(summary, "div", /^ID/).getByText(project.id)).toBeVisible();
  await expect(innermost(summary, "div", /description/i).locator("textarea")).toContainText(
    project.description!,
  );
  await expectEditableFields(summary, project);
  await expect(innermost(summary, "div", /created/i).getByText(relativeTime).first()).toBeVisible();
  await expect(
    innermost(summary, "div", /last updated/i).getByText(relativeTime).first(),
  ).toBeVisible();
  await expect(summary.locator("button", { hasText: /update/i })).toBeVisible();
  await expect(summary.locator("button", { hasText: /delete/i })).toBeVisible();
}

/** Checks the fields that the edit form and the create form show alike */
async function expectEditableFields(
  form: Locator,
  project: Pick<
    AdminProject,
    "is_active" | "is_pulse_allowed" | "qpu_seconds" | "admin_email" | "user_emails"
  >,
) {
  await expect(
    innermost(form, "div", /live/i).locator(
      `button[role="switch"][data-state="${project.is_active ? "checked" : "unchecked"}"]`,
    ),
  ).toBeVisible();
  await expect(form.locator("button#is_pulse_allowed[role='switch']")).toHaveAttribute(
    "data-state",
    project.is_pulse_allowed ? "checked" : "unchecked",
  );
  await expect(innermost(form, "div", /qpu seconds/i).locator("input")).toHaveValue(
    `${project.qpu_seconds}`,
  );
  await expect(innermost(form, "div", /admin/i).locator("input")).toHaveValue(project.admin_email);

  const members = innermost(form, "div", /member emails/i);
  for (const [index, email] of project.user_emails.entries()) {
    const wrapper = members.locator(`#user_emails-${index}-wrapper`);
    await expect(wrapper.locator(`#user_emails-${index}`)).toHaveValue(email);
    await expect(wrapper.locator(`#user_emails-${index}-del-btn[aria-label="X"]`)).toBeVisible();
  }
  await expect(members.locator('button[aria-label="Plus"]')).toBeVisible();
}

async function expectInTopBar(page: Page, name: string, isListed: boolean) {
  await page.locator('[data-testid="topbar"] button', { hasText: /project:/i }).click();
  const option = page.locator('#project-selector [role="option"]', { hasText: name });
  await (isListed ? expect(option).toBeVisible() : expect(option).toHaveCount(0));
  // closes the drop down
  await page.locator('#project-selector [role="option"]', { hasText: /none/i }).click();
}
