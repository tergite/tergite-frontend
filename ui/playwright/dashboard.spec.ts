import type { Locator } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import {
  type Project,
  type User,
  type UserRequest,
  UserRequestStatus,
  UserRole,
} from "./types";

// an admin with projects, a member of several, and a user of none
const users = readFixture<User[]>("users").filter((v) =>
  ["jane.doe@example.com", "paul.doe@example.com", "julie.doe@example.com"].includes(v.email),
);
const projects = readFixture<Project[]>("projects");
const userRequests = readFixture<UserRequest[]>("user-requests");

for (const user of users) {
  const userProjects = projects.filter((v) => v.user_ids.includes(user.id) && v.is_active);
  const username = user.email.split("@")[0];
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  // the admin badge counts the pending requests awaiting this user's decision
  const requestsCount = userRequests.filter(
    (v) => v.status === UserRequestStatus.PENDING && v.target_user_ids.includes(user.id),
  ).length;

  test.describe(`dashboard-layout for ${username}`, () => {
    test.beforeEach(async ({ page, loginAs }) => {
      await Promise.all([
        waitForApi(page, "GET", "/me/projects/"),
        waitForApi(page, "GET", "/devices/"),
        loginAs(user, "./"),
      ]);
    });

    test("renders the sidebar in desktop mode", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const sidebar = page.getByTestId("sidebar");
      await expect(sidebar).toBeVisible();
      await expect(sidebar.getByText("WACQT").first()).toBeVisible();
      await expect(
        sidebar.getByText(/Wallenberg Centre for Quantum Technology/i).first(),
      ).toBeVisible();
      await expectTextVisible(sidebar.locator("nav a[href='/ui/']"), /dashboard/i);
      await expectTextVisible(sidebar.locator("nav a[href='/ui/devices']"), /devices/i);

      const access = sidebar.locator("nav [data-testid='access-submenu']");
      await expectTextVisible(access.locator("button"), /access/i);
      await expectTextVisible(access.locator("a[href='/ui/projects']"), /projects/i);
      await expectTextVisible(access.locator("a[href='/ui/tokens']"), /tokens/i);
      await expectTextVisible(access.locator("a[href='/ui/requests']"), /requests/i);

      if (isAdmin) {
        const admin = sidebar.locator("nav [data-testid='admin-submenu']");
        await expectTextVisible(admin.locator("button"), /admin/i);
        await expectTextVisible(admin.locator("a[href='/ui/admin-projects']"), /projects/i);
        await expectTextVisible(admin.locator("a[href='/ui/admin-control']"), /control/i);
        await expectTextVisible(admin.locator("a[href='/ui/admin-requests']"), /requests/i);
      }

      await expect(sidebar.locator("[aria-label='PanelLeftClose']")).toBeVisible();
    });

    test("renders the mobile-menu in mobile mode", async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 740 });
      const toggle = page.locator("button", { hasText: "Toggle Menu" });
      const menu = page.getByTestId("mobile-menu");
      await expect(toggle).toBeVisible();
      await expect(menu).toHaveCount(0);

      await toggle.click();

      await expectTextVisible(menu.locator("a[href='/ui/']"), /dashboard/i);
      await expectTextVisible(menu.locator("a[href='/ui/devices']"), /devices/i);

      const access = menu.locator("nav [data-testid='access-submenu']");
      await expectTextVisible(access.locator("a[href='/ui/projects']"), /projects/i);
      await expectTextVisible(access.locator("a[href='/ui/tokens']"), /tokens/i);
      await expectTextVisible(access.locator("a[href='/ui/requests']"), /requests/i);

      if (isAdmin) {
        const admin = menu.locator("nav [data-testid='admin-submenu']");
        await expectTextVisible(admin.locator("a[href='/ui/admin-requests']"), /requests/i);
        await expectTextVisible(admin.locator("a[href='/ui/admin-projects']"), /projects/i);
        await expectTextVisible(admin.locator("a[href='/ui/admin-control']"), /control/i);
      }
    });

    test("renders the collapsed sidebar when collapse button is pressed", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      const sidebar = page.getByTestId("sidebar");
      const nav = sidebar.locator("nav");
      const collapseIcon = sidebar.locator("[aria-label='PanelLeftClose']");
      const expandIcon = sidebar.locator("[aria-label='PanelRightClose']");
      const linkText = (href: string, text: RegExp) =>
        nav.locator(`a[href='/ui${href}'] div`, { hasText: text }).first();

      const expectIsUncollapsed = async () => {
        await expect(linkText("/", /dashboard/i)).toHaveText("DashboardDashboard");
        await expect(linkText("/devices", /devices/i)).toHaveText("DevicesDevices");

        const access = nav.locator("[data-testid='access-submenu']");
        await expectTextVisible(access.locator("button"), /access/i);
        await expect(linkText("/projects", /projects/i)).toHaveText("ProjectsProjects");
        await expect(linkText("/tokens", /tokens/i)).toHaveText("TokensTokens");
        await expect(linkText("/requests", /requests/i)).toHaveText("RequestsRequests");

        if (isAdmin) {
          const admin = nav.locator("[data-testid='admin-submenu']");
          await expectTextVisible(admin.locator("button"), /admin/i);
          await expect(admin.locator("a[href='/ui/admin-requests']")).toHaveText(
            `RequestsRequests ${requestsCount}`,
          );
          await expect(admin.locator("a[href='/ui/admin-projects']")).toHaveText("ProjectsProjects");
          await expect(admin.locator("a[href='/ui/admin-control']")).toHaveText("ControlControl");
        }
        await expect(collapseIcon).toBeVisible();
        await expect(expandIcon).toHaveCount(0);
      };

      const expectIsCollapsed = async () => {
        await expect(collapseIcon).toHaveCount(0);
        await expect(expandIcon).toBeVisible();

        for (const icon of ["Home", "Cpu", "FolderKanban", "KeySquare", "ClipboardList"]) {
          await expect(nav.locator(`[aria-label='${icon}']`)).toBeVisible();
        }
        if (isAdmin) {
          await expect(nav.locator("[aria-label='HardHat']")).toBeVisible();
          await expect(nav.locator("[aria-label='SlidersHorizontal']")).toBeVisible();
        }

        await expect(nav.locator("div", { hasText: /dashboard/i }).first()).toHaveText("Dashboard");
        await expect(nav.locator("div", { hasText: /devices/i }).first()).toHaveText("Devices");
        await expect(nav.locator("a[href='/ui/projects']")).toHaveText("Projects");
        await expect(nav.locator("a[href='/ui/tokens']")).toHaveText("Tokens");
        await expect(nav.locator("a[href='/ui/requests']")).toHaveText("Requests");

        if (isAdmin) {
          await expect(nav.locator("a[href='/ui/admin-requests']")).toHaveText("Requests ");
          await expect(nav.locator("a[href='/ui/admin-projects']")).toHaveText("Projects");
          await expect(nav.locator("a[href='/ui/admin-control']")).toHaveText("Control");
        }
      };

      await expectIsUncollapsed();
      await collapseIcon.locator("..").click();
      await expectIsCollapsed();
      await expandIcon.locator("..").click();
      await expectIsUncollapsed();
    });

    test("renders the topbar", async ({ page }) => {
      const topbar = page.getByTestId("topbar");
      await expect(topbar.getByRole("combobox")).toBeVisible();
      await expect(topbar.locator("[aria-label='UserRound']")).toBeVisible();
      await expect(topbar.locator("[aria-label='Moon']")).toBeVisible();
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

    test("renders the topbanner", async ({ page }) => {
      const banner = page.getByTestId("top-banner");
      await expect(banner.getByText(/api token/i).first()).toBeVisible();
      await expect(banner.locator("input")).toBeVisible();
      await expect(banner.locator("[aria-label='RefreshCcw']")).toBeVisible();
      await expect(banner.locator("[aria-label='Copy']")).toBeVisible();
    });

    test("renders the notifications bell in the topbar", async ({ page }) => {
      const topbar = page.getByTestId("topbar");
      await expect(topbar.getByTestId("notices-bell-icon")).toBeVisible();
      await expect(page.locator("#notifications-panel")).toHaveCount(0);
    });

    test("names the release at the foot of the sidebar", async ({ page }) => {
      await page.setViewportSize({ width: 1080, height: 750 });
      await expect(page.locator("[data-cy-release]")).toHaveText(/^Release \d{4}\.\d{2}$/);
    });

    test("logout button logs current user out", async ({ page }) => {
      await page.getByTestId("topbar").locator("[aria-label='UserRound']").click({ force: true });
      await Promise.all([
        waitForApi(page, "POST", "/auth/logout"),
        page.getByText(/logout/i).first().click(),
      ]);
      await expect(page).toHaveURL("login");
    });

    test("current project can be selected from list of projects", async ({ page }) => {
      const projectSelectBtn = page.getByTestId("topbar").getByRole("combobox");
      await expect(projectSelectBtn).toHaveText("Project Select project");

      for (const project of userProjects) {
        await projectSelectBtn.click();
        await page.locator("#project-selector").getByText(project.name).first().click();
        await expect(projectSelectBtn).toHaveText(`Project ${project.name}`);
      }
    });

    test("generates new api token on token-refresh button click", async ({ page }) => {
      const projectSelectBtn = page.getByTestId("topbar").getByRole("combobox");
      const newTokenBtn = page.locator('[data-testid="top-banner"] [aria-label="RefreshCcw"]');
      const appTokenInput = page.locator('[data-testid="top-banner"] input#api-token');

      for (const project of userProjects) {
        await projectSelectBtn.click();
        await page.locator("[data-radix-popper-content-wrapper]").getByText(project.name).first().click();
        await newTokenBtn.click();
        await expect(appTokenInput).not.toHaveValue("");
      }
    });

    test("copies current api token on token-copy button click", async ({ page }) => {
      await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
      const projectSelectBtn = page.getByTestId("topbar").getByRole("combobox");
      const newTokenBtn = page.locator('[data-testid="top-banner"] [aria-label="RefreshCcw"]');
      const copyBtn = page.locator('[data-testid="top-banner"] [aria-label="Copy"]');
      const appTokenInput = page.locator('[data-testid="top-banner"] input#api-token');

      for (const project of userProjects) {
        await projectSelectBtn.click();
        await page.locator("[data-radix-popper-content-wrapper]").getByText(project.name).first().click();
        const previousToken = await appTokenInput.inputValue();
        await newTokenBtn.click();
        // the copy button copies whatever token is shown, so the new one must be shown first
        await expect(appTokenInput).not.toHaveValue(previousToken);
        await copyBtn.click();
        const copiedText = await page.evaluate(() => navigator.clipboard.readText());
        await expect(appTokenInput).toHaveValue(copiedText);
      }
    });
  });
}

async function expectTextVisible(container: Locator, text: RegExp) {
  await expect(container.getByText(text).first()).toBeVisible();
}
