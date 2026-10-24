/// <reference types="cypress" />

import userList from "../fixtures/users.json";
import projectList from "../fixtures/projects.json";
import userRequestList from "../fixtures/user-requests.json";
import { generateJwt, getUsername } from "../../dev/mock-api/utils";
import {
  UserRequest,
  UserRequestStatus,
  UserRole,
  type Project,
  type User,
} from "../../types";

// an admin with projects, a member of several, and a user of none
const users = ([...userList] as User[]).filter((v) =>
  ["jane.doe@example.com", "paul.doe@example.com", "julie.doe@example.com"].includes(v.email)
);
const projects = [...projectList] as Project[];
const userRequests = [...userRequestList] as UserRequest[];

users.forEach((user) => {
  const userProjects = projects.filter(
    (v) => v.user_ids.includes(user.id) && v.is_active,
  );
  const username = getUsername(user);
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  // the admin badge counts the pending requests awaiting this user's decision
  const pendingUserRequests = userRequests.filter(
    (v) =>
      v.status === UserRequestStatus.PENDING &&
      v.target_user_ids.includes(user.id),
  );
  const requestsCount = pendingUserRequests.length;

  describe(`dashboard-layout for ${username}`, () => {
    const dashboardUrl = Cypress.config("baseUrl");

    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/*`).as("my-project-list");
      cy.intercept("GET", `${apiBaseUrl}/me/jobs/*`).as("my-jobs-list");
      cy.intercept("POST", `${apiBaseUrl}/auth/logout`).as("logout");

      if (user.id) {
        cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then(
          (jwtToken) => {
            cy.setCookie(cookieName, jwtToken as string, {
              domain,
              httpOnly: true,
              secure: false,
              sameSite: "lax",
            });
          },
        );
      }

      // We need to reset the mongo database before each test
      cy.request(`${dbResetUrl}`);

      cy.visit("/");
      cy.wait("@my-project-list");
      cy.wait("@devices-list");
    });

    it("renders the sidebar in desktop mode", () => {
      cy.viewport(1080, 750);
      cy.get("[data-testid='sidebar']").should("be.visible");
      cy.get("[data-testid='sidebar']").within(() => {
        cy.contains("WACQT").should("be.visible");
        cy.contains(/Wallenberg Centre for Quantum Technology/i).should(
          "be.visible",
        );
        cy.get("nav a[href='/']")
          .contains(/dashboard/i)
          .should("be.visible");
        cy.get("nav a[href='/devices']")
          .contains(/devices/i)
          .should("be.visible");

        cy.get("nav [data-testid='access-submenu']").within(() => {
          cy.get("button")
            .contains(/access/i)
            .should("be.visible");

          cy.get("a[href='/projects']")
            .contains(/projects/i)
            .should("be.visible");
          cy.get("a[href='/tokens']")
            .contains(/tokens/i)
            .should("be.visible");
          cy.get("a[href='/requests']")
            .contains(/requests/i)
            .should("be.visible");
        });

        if (isAdmin) {
          cy.get("nav [data-testid='admin-submenu']").within(() => {
            cy.get("button").contains(/admin/i).should("be.visible");

            cy.get("a[href='/admin-projects']")
              .scrollIntoView()
              .contains(/projects/i)
              .should("be.visible");
            cy.get("a[href='/admin-control']")
              .scrollIntoView()
              .contains(/control/i)
              .should("be.visible");
            cy.get("a[href='/admin-requests']")
              .scrollIntoView()
              .contains(/requests/i)
              .should("be.visible");
          });
        }

        // collapse button
        cy.get("[aria-label='PanelLeftClose']").should("be.visible");
      });
    });

    it("renders the mobile-menu in mobile mode", () => {
      cy.viewport(360, 740);
      cy.contains("button", "Toggle Menu").should("be.visible");

      cy.get('[data-testid="mobile-menu"]').should("not.exist");

      cy.contains("button", "Toggle Menu").realClick();

      cy.get('[data-testid="mobile-menu"]').within(() => {
          cy.get("a[href='/']")
            .contains(/dashboard/i)
            .should("be.visible");

          cy.get("a[href='/devices']")
            .contains(/devices/i)
            .should("be.visible");

        cy.get('nav [data-testid="access-submenu"]').within(() => {
          cy.get("a[href='/projects']")
            .scrollIntoView()
            .contains(/projects/i)
            .should("be.visible");
          cy.get("a[href='/tokens']")
            .scrollIntoView()
            .contains(/tokens/i)
            .should("be.visible");

          cy.get("a[href='/requests']")
            .scrollIntoView()
            .contains(/requests/i)
            .should("be.visible");
        });


        if (isAdmin) {
          cy.get('nav [data-testid="admin-submenu"]').within(() => {
            cy.get("a[href='/admin-requests']")
              .scrollIntoView()
              .contains(/requests/i)
              .should("be.visible");

            cy.get("a[href='/admin-projects']")
              .scrollIntoView()
              .contains(/projects/i)
              .should("be.visible");

            cy.get("a[href='/admin-control']")
              .scrollIntoView()
              .contains(/control/i)
              .should("be.visible");
          });
        }
      });
    });

    it("renders the collapsed sidebar when collapse button is pressed", () => {
      cy.viewport(1080, 750);
      cy.get("[data-testid='sidebar']").within(() => {
        const assertIsUncollapsed = () => {
          cy.get("nav a[href='/']")
            .contains("div", /dashboard/i)
            .should("have.text", "DashboardDashboard");
          cy.get("nav a[href='/devices']")
            .contains("div", /devices/i)
            .should("have.text", "DevicesDevices");

          cy.get("nav [data-testid='access-submenu']").within(() => {
            cy.get("button")
              .contains(/access/i)
              .should("be.visible");

            cy.get("a[href='/projects']")
              .contains("div", /projects/i)
              .should("have.text", "ProjectsProjects");

            cy.get("a[href='/tokens']")
              .contains("div", /tokens/i)
              .should("have.text", "TokensTokens");

            cy.get("a[href='/requests']")
              .contains("div", /requests/i)
              .should("have.text", "RequestsRequests");
          });

          if (isAdmin) {
            cy.get("nav [data-testid='admin-submenu']").within(() => {
              cy.get("button").contains(/admin/i).should("be.visible");

              cy.get("a[href='/admin-requests']").should(
                "have.text",
                `RequestsRequests ${requestsCount}`
              );

              cy.get("a[href='/admin-projects']").should(
                "have.text",
                "ProjectsProjects"
              );

              cy.get("a[href='/admin-control']").should(
                "have.text",
                "ControlControl"
              );
            });
          }
          cy.get("[aria-label='PanelLeftClose']").should("be.visible");
          cy.get("[aria-label='PanelRightClose']").should("not.exist");
        };

        const assertIsCollapsed = () => {
          cy.get("[aria-label='PanelLeftClose']").should("not.exist");
          cy.get("[aria-label='PanelRightClose']").should("be.visible");

          cy.get("nav [aria-label='Home']").should("be.visible");
          cy.get("nav [aria-label='Cpu']").should("be.visible");
          cy.get("nav [aria-label='FolderKanban']").should("be.visible");
          cy.get("nav [aria-label='KeySquare']").should("be.visible");
          cy.get("nav [aria-label='ClipboardList']").should("be.visible");
          if (isAdmin) {
            // cy.get("nav [aria-label='HelpingHand']").should("be.visible");
            cy.get("nav [aria-label='HardHat']").should("be.visible");
            cy.get("nav [aria-label='SlidersHorizontal']").should("be.visible");
          }

          cy.get("nav")
            .contains("div", /dashboard/i)
            .should("have.text", "Dashboard");
          cy.get("nav")
            .contains("div", /devices/i)
            .should("have.text", "Devices");

          cy.get("nav a[href='/projects']").should("have.text", "Projects");
          cy.get("nav a[href='/tokens']").should("have.text", "Tokens");
          cy.get("nav a[href='/requests']").should("have.text", "Requests");

          if (isAdmin) {
            cy.get("nav a[href='/admin-requests']").should(
              "have.text",
              "Requests "
            );

            cy.get("nav a[href='/admin-projects']").should(
              "have.text",
              "Projects"
            );

            cy.get("nav a[href='/admin-control']").should(
              "have.text",
              "Control"
            );
          }
        };

        // run
        assertIsUncollapsed();
        cy.get("[aria-label='PanelLeftClose']").parent().realClick();
        assertIsCollapsed();
        cy.get("[aria-label='PanelRightClose']").parent().click();
        assertIsUncollapsed();
      });
    });

    it("renders the topbar", () => {
      cy.get('[data-testid="topbar"]').within(() => {
        cy.contains(/project:/i).should("be.visible");
        cy.get("[aria-label='UserRound']").should("be.visible");
        cy.get("[aria-label='Moon']").should("be.visible");
      });
    });

    it("toggles dark mode", () => {
      cy.get('[aria-label="Moon"]').as("toDarkBtn");
      cy.get('[aria-label="Sun"]').should("not.exist");

      cy.get("@toDarkBtn").click();
      cy.get("html.dark").should("be.visible");
      cy.get("@toDarkBtn").should("not.exist");

      cy.get('[aria-label="Sun"]').as("toLightBtn");
      cy.get("@toLightBtn").should("be.visible");

      cy.get("@toLightBtn").click();
      cy.get("html.dark").should("not.exist");
      cy.get("@toDarkBtn").should("be.visible");
      cy.get("@toLightBtn").should("not.exist");
    });

    it("renders the topbanner", () => {
      cy.get('[data-testid="top-banner"]').within(() => {
        cy.contains(/api token/i).should("be.visible");
        cy.get("input").should("be.visible");
        cy.get("[aria-label='RefreshCcw']").should("be.visible");
        cy.get("[aria-label='Copy']").should("be.visible");
        // Notice count badge (bell icon) is always visible in the banner
        cy.get('[data-testid="notices-bell-icon"]').should("exist");
      });
    });

    it("logout button logs current user out", () => {
      cy.get("[data-testid='topbar'] [aria-label='UserRound']").click({
        force: true,
      });
      cy.contains(/logout/i).click();
      cy.wait("@logout");
      cy.url().should("equal", `${dashboardUrl}login`);
    });

    it("current project can be selected from list of projects", () => {
      cy.get('[data-testid="topbar"]')
        .contains("button", /project:/i)
        .as("projectSelectBtn");
      cy.get("@projectSelectBtn").should(
        "have.text",
        "Project: Select project",
      );

      for (const project of userProjects) {
        cy.get("@projectSelectBtn").click();
        cy.get("#project-selector").within(() => {
          cy.contains(project.name).as("project-btn");
          cy.get("@project-btn").click();
        });
        cy.wait(100);
        cy.get("@projectSelectBtn").should(
          "have.text",
          `Project: ${project.name}`,
        );
      }
    });

    it("generates new api token on token-refresh button click", () => {
      cy.get('[data-testid="topbar"]')
        .contains("button", /project:/i)
        .as("projectSelectBtn");

      cy.get('[data-testid="top-banner"] [aria-label="RefreshCcw"]').as(
        "newTokenBtn",
      );

      cy.get('[data-testid="top-banner"] input#api-token').as("appTokenInput");

      for (const project of userProjects) {
        cy.get("@projectSelectBtn").click();
        cy.get("[data-radix-popper-content-wrapper]")
          .contains(project.name)
          .click()
          .then(() => {
            cy.get("@newTokenBtn")
              .click()
              .then(() => {
                cy.wait(500);
                cy.get("@appTokenInput")
                  .invoke("val")
                  .then((value) => expect(value).not.to.eql(""));
              });
          });
      }
    });

    it("copies current api token on token-copy button click", () => {
      cy.get('[data-testid="topbar"]')
        .contains("button", /project:/i)
        .as("projectSelectBtn");

      cy.get('[data-testid="top-banner"] [aria-label="RefreshCcw"]').as(
        "newTokenBtn",
      );

      cy.get('[data-testid="top-banner"] [aria-label="Copy"]').as("copyBtn");

      cy.get('[data-testid="top-banner"] input#api-token').as("appTokenInput");

      for (const project of userProjects) {
        cy.get("@projectSelectBtn").click();
        cy.get("[data-radix-popper-content-wrapper]")
          .contains(project.name)
          .click();
        cy.get("@newTokenBtn").click();
        cy.get("@copyBtn").click();
        cy.clipboard().then((text) => {
          cy.get("@appTokenInput")
            .invoke("val")
            .then((value) => expect(value).to.eql(text));
        });
      }
    });
  });
});
