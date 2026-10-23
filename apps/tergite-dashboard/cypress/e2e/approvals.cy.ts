/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userRequestList from "../fixtures/user-requests.json";
import userList from "../fixtures/users.json";
import { generateJwt } from "../../dev/mock-api/utils";
import { UserRole, type User, type UserRequest } from "../../types";

const users = [...userList] as User[];
const requests = [...userRequestList] as UserRequest[];

// a project admin, not a superuser, so only the requests on their own projects reach them
const approvers = users.filter(
  (user) =>
    !user.roles.includes(UserRole.ADMIN) &&
    requests.some((v) => v.target_user_ids.includes(user.id))
);

function login(user: User, path: string) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const dbResetUrl = Cypress.env("DB_RESET_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/me/profile`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/me/requests/?*`).as("my-requests");
  cy.intercept("PUT", `${apiBaseUrl}/me/requests/*`).as("request-react");

  cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then((jwt) => {
    cy.setCookie(cookieName, jwt as string, {
      domain,
      httpOnly: true,
      secure: false,
      sameSite: "lax",
    });
  });

  cy.request(`${dbResetUrl}`);
  cy.visit(path);
  cy.wait("@my-user-info");
  cy.wait("@my-requests");
}

approvers.forEach((user) => {
  const awaiting = requests.filter((v) => v.target_user_ids.includes(user.id));
  const pending = awaiting.filter((v) => v.status === "pending");

  describe(`approvals page for ${user.id}`, () => {
    beforeEach(() => {
      cy.viewport(1728, 1000);
      login(user, "/approvals");
    });

    it("is reachable from the pending count on the projects page", () => {
      cy.visit("/projects");
      cy.get("[data-cy-approvals-link]")
        .should("contain.text", `${pending.length} awaiting your approval`)
        .click();
      cy.url().should("match", /\/approvals$/);
    });

    it("lists every request awaiting this user", () => {
      cy.get("tbody tr").should("have.length", awaiting.length);
    });

    it("shows the placeholder until a row is picked", () => {
      cy.get("#sidebar-placeholder").should("be.visible");
      cy.get("#approval-summary").should("not.exist");
    });

    it("shows who asked when a row is picked", () => {
      cy.get("tbody tr").first().click();
      cy.get("#approval-summary").within(() => {
        cy.contains(pending[0].requester_name).should("be.visible");
        cy.contains("pending").should("be.visible");
      });
    });

    it("approving a request marks it approved and clears the pending count", () => {
      cy.get("tbody tr").first().click();
      cy.get("[data-cy-approve]").click();
      cy.wait("@request-react");

      cy.get("#sidebar-placeholder").should("be.visible");
      cy.get("tbody tr").first().should("contain.text", "approved");
      cy.visit("/projects");
      cy.get("[data-cy-approvals-link]").should("not.exist");
    });

    it("rejecting a request marks it rejected", () => {
      cy.get("tbody tr").first().click();
      cy.get("[data-cy-reject]").click();
      cy.wait("@request-react");

      cy.get("tbody tr").first().should("contain.text", "rejected");
    });
  });
});
