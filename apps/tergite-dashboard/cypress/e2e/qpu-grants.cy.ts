/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import { generateJwt } from "../../api/utils";
import { UserRole, type User } from "../../types";

const users = [...userList] as User[];
const admin = users.find((v) => v.roles.includes(UserRole.ADMIN)) as User;
const plain = users.find((v) => !v.roles.includes(UserRole.ADMIN)) as User;

// no personal projects exist in the shared fixture -- adding one perturbs the
// admin-projects row expectations -- so the e2e covers the UI wiring and the skipped
// path. The granted path is covered by the MSS tests, which own that behaviour.
function login(user: User) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const dbResetUrl = Cypress.env("DB_RESET_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/me`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/admin/projects/*`).as("admin-projects");
  cy.intercept("POST", `${apiBaseUrl}/admin/qpu-seconds-grants/`).as("grant");

  cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then((jwt) => {
    cy.setCookie(cookieName, jwt as string, {
      domain,
      httpOnly: true,
      secure: false,
      sameSite: "lax",
    });
  });

  cy.request(`${dbResetUrl}`);
  cy.wait(500);
  cy.visit("/admin-projects");
  cy.wait("@my-user-info");
}

/** Adds one email row to a MultiInput, the way the component requires */
function typeEmail(email: string, index = 0) {
  cy.get("#grant-emails-wrapper").within(() => {
    cy.get('button[aria-label="Plus"]').click();
  });
  cy.get(`#grant-emails-${index}`).clear().type(email);
}

describe("granting QPU time as an admin", () => {
  beforeEach(() => {
    login(admin);
    cy.wait("@admin-projects");
    cy.get("[data-cy-grant-qpu-time]").click();
  });

  it("opens the grant form in place of the project sidebar", () => {
    cy.get("#grant-qpu-seconds").should("be.visible");
    cy.get("#project-summary").should("not.exist");
  });

  it("asks for emails only when targeting named users", () => {
    cy.get("#grant-emails").should("exist");

    cy.get("#grant-target").click();
    cy.contains('[role="option"]', /all personal projects/i).click();

    cy.get("#grant-emails").should("not.exist");
  });

  it("refuses a grant with no emails when targeting named users", () => {
    cy.get("#grant-reason").type("new QPU online");
    cy.get("[data-cy-grant-submit]").click();

    cy.contains(/at least one email is required/i).should("be.visible");
  });

  it("refuses a non-positive number of seconds", () => {
    cy.get("#grant-seconds").clear().type("0");
    typeEmail(plain.email);
    cy.get("#grant-reason").type("nothing at all");
    cy.get("[data-cy-grant-submit]").click();

    cy.contains(/must be more than zero/i).should("be.visible");
  });

  it("reports users who have no personal project rather than failing", () => {
    typeEmail(plain.email);
    cy.get("#grant-reason").type("new QPU online");
    cy.get("[data-cy-grant-submit]").click();

    cy.wait("@grant").its("response.statusCode").should("eq", 201);
    cy.get("[data-cy-grant-report]").within(() => {
      cy.contains(/0 projects granted/i).should("be.visible");
      cy.contains(plain.email).should("be.visible");
      cy.contains(/never logged in/i).should("be.visible");
    });
  });

  it("reports an unknown address", () => {
    typeEmail("nobody@example.com");
    cy.get("#grant-reason").type("typo");
    cy.get("[data-cy-grant-submit]").click();

    cy.wait("@grant");
    cy.get("[data-cy-grant-report]").within(() => {
      cy.contains(/no such user/i).should("be.visible");
    });
  });

  it("confirms before granting to every personal project", () => {
    cy.get("#grant-target").click();
    cy.contains('[role="option"]', /all personal projects/i).click();
    cy.get("#grant-reason").type("gift for the new QPU");

    cy.get("[data-cy-grant-submit]").click();
    cy.get("#confirm-dialog").should("be.visible");
    cy.contains("#confirm-dialog", /cannot be undone/i).should("be.visible");

    cy.contains("#confirm-dialog button", /confirm/i).click();
    cy.wait("@grant").its("response.statusCode").should("eq", 201);

    cy.get("#confirm-dialog").should("not.exist");
    cy.get("[data-cy-grant-report]").should("be.visible");
    cy.get("[data-cy-grant-submit]").should("be.disabled");
  });

  it("needs a fresh edit before it will grant again", () => {
    typeEmail(plain.email);
    cy.get("#grant-reason").type("new QPU online");
    cy.get("[data-cy-grant-submit]").click();

    cy.wait("@grant");
    cy.get("[data-cy-grant-submit]").should("be.disabled");

    cy.get("#grant-reason").type("second thoughts");
    cy.get("[data-cy-grant-submit]").should("be.enabled");
  });

  it("gives a deliberate second grant its own idempotency key", () => {
    typeEmail(plain.email);
    cy.get("#grant-reason").type("first");
    cy.get("[data-cy-grant-submit]").click();

    cy.wait("@grant").then((first) => {
      typeEmail(plain.email);
      cy.get("#grant-reason").type("second");
      cy.get("[data-cy-grant-submit]").click();

      cy.wait("@grant").then((second) => {
        expect(second.request.headers["idempotency-key"]).to.not.equal(
          first.request.headers["idempotency-key"]
        );
      });
    });
  });

  it("closes the form on cancel", () => {
    cy.contains("#grant-qpu-seconds button", /cancel/i).click();

    cy.get("#grant-qpu-seconds").should("not.exist");
  });
});

describe("granting QPU time as a non-admin", () => {
  it("does not offer the grant control", () => {
    login(plain);

    cy.get("[data-cy-grant-qpu-time]").should("not.exist");
  });
});
