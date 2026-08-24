/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userRequestList from "../fixtures/user-requests.json";
import userList from "../fixtures/users.json";
import { generateJwt } from "../../api/utils";
import { type User, type UserRequest } from "../../types";

const users = [...userList] as User[];
const requests = [...userRequestList] as UserRequest[];

// the fixture hangs almost every request off one requester; iterating users with no
// requests would only assert the empty table over and over
const requesters = users.filter((user) =>
  requests.some((v) => v.requester_id === user.id)
);

function login(user: User) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const dbResetUrl = Cypress.env("DB_RESET_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/me`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/me/requests/?*`).as("my-requests");

  cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then((jwt) => {
    cy.setCookie(cookieName, jwt as string, {
      domain,
      httpOnly: true,
      secure: false,
      sameSite: "lax",
    });
  });

  cy.request(`${dbResetUrl}`);
  cy.visit("/requests");
  cy.wait("@my-user-info");
  cy.wait("@my-requests");
}

requesters.forEach((user) => {
  const own = requests.filter((v) => v.requester_id === user.id);

  describe(`my requests page for ${user.id}`, () => {
    beforeEach(() => {
      cy.viewport(1728, 1000);
      login(user);
    });

    it("is reachable from the Access group in the sidebar", () => {
      cy.visit("/");
      cy.get("[data-testid='sidebar'] a[href='/requests']").click();
      cy.url().should("match", /\/requests$/);
    });

    it("lists every request this user made", () => {
      cy.get("tbody tr").should("have.length", own.length);
    });

    it("shows the placeholder until a row is picked", () => {
      cy.get("#sidebar-placeholder").should("be.visible");
      cy.get("#request-summary").should("not.exist");
    });

    it("shows what was asked for, and the outcome, when a row is picked", () => {
      // newest first, matching the API's sort
      const newest = [...own].sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      )[0];

      cy.get("tbody tr").first().click();
      cy.get("#request-summary").within(() => {
        cy.contains(newest.status).should("be.visible");
        for (const [key, value] of Object.entries(
          newest.request as Record<string, unknown>
        )) {
          // DetailItem capitalises the label, so match without regard to case
          cy.contains(new RegExp(key.replace(/_/g, " "), "i")).should("exist");
          cy.contains(
            Array.isArray(value) ? value.join(", ") : `${value}`
          ).should("exist");
        }
      });
    });

    it("offers no approve or reject controls on your own request", () => {
      cy.get("tbody tr").first().click();
      cy.get("[data-cy-approve]").should("not.exist");
      cy.get("[data-cy-reject]").should("not.exist");
    });
  });
});
