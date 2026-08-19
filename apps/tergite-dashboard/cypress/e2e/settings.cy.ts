/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import { generateJwt } from "../../api/utils";
import { NotificationType, type User } from "../../types";

// preferences behave identically for everyone, so one representative user is enough
const [user] = [...userList] as User[];
// one type the recipient can act on, one that only reports an outcome
const SAMPLE_TYPES = [
  NotificationType.PROJECT_ACCESS_REQUESTED,
  NotificationType.QPU_SECONDS_GRANTED,
];

function login(user: User, path: string) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const dbResetUrl = Cypress.env("DB_RESET_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/me`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/me/notification-preferences/`).as("prefs");
  cy.intercept("PUT", `${apiBaseUrl}/me/notification-preferences/`).as(
    "prefs-update",
  );

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

  cy.request(`${dbResetUrl}`);
  cy.wait(500);
  cy.visit(path);
  cy.wait("@my-user-info");
}

describe(`settings for ${user.email.split("@")[0]}`, () => {
  beforeEach(() => {
    login(user, "/settings");
    cy.wait("@prefs");
  });

  it("is reachable from the user menu", () => {
    cy.visit("/");
    cy.get("[data-testid='topbar'] [aria-label='UserRound']").click({
      force: true,
    });
    cy.get("[data-cy-settings-link]").click();

    cy.url().should("contain", "/settings");
    cy.contains("Email notifications").should("be.visible");
  });

  it("shows an email switch for every notification type", () => {
    cy.get("[data-cy-email-switch]").should(
      "have.length",
      Object.values(NotificationType).length,
    );
    cy.get("[data-cy-email-switch]").each((element) => {
      cy.wrap(element).should("have.attr", "data-state", "checked");
    });
  });

  SAMPLE_TYPES.forEach((type) => {
    it(`turns email off for ${type}`, () => {
      cy.get(`[data-cy-email-switch='${type}']`).click();
      cy.wait("@prefs-update");

      cy.get(`[data-cy-email-switch='${type}']`).should(
        "have.attr",
        "data-state",
        "unchecked",
      );
    });

    it(`keeps the opt-out for ${type} after a reload`, () => {
      cy.get(`[data-cy-email-switch='${type}']`).click();
      cy.wait("@prefs-update");

      cy.reload();
      cy.wait("@prefs");

      cy.get(`[data-cy-email-switch='${type}']`).should(
        "have.attr",
        "data-state",
        "unchecked",
      );
    });
  });

  it("leaves the other types alone", () => {
    const [changed, untouched] = SAMPLE_TYPES;
    cy.get(`[data-cy-email-switch='${changed}']`).click();
    cy.wait("@prefs-update");

    cy.get(`[data-cy-email-switch='${untouched}']`).should(
      "have.attr",
      "data-state",
      "checked",
    );
  });
});

describe("settings when unauthenticated", () => {
  it("redirects to login", () => {
    cy.visit("/settings");

    cy.url().should("contain", "/login");
  });
});
