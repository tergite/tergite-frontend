/// <reference types="cypress" />

import { generateJwt, getUsername } from "../../api/utils";
import { type User } from "../../types";
import userList from "../fixtures/users.json";

const users = [...userList] as User[];

users.forEach((user) => {
  const username = getUsername(user);

  describe(`error-alert page for '${username}'`, () => {
    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices/*`, (req) => {
        req.reply(500, { detail: "dummy server error" });
      }).as("devices-list");

      cy.intercept("GET", `${apiBaseUrl}/devices/loke`, (req) => {
        req.reply(500, { detail: "dummy server error" });
      }).as("loke-device");

      if (user.id) {
        cy.wrap(generateJwt(user, cookieExpiry, { secret, audience })).then(
          (jwtToken) => {
            cy.setCookie(cookieName, jwtToken as string, {
              domain,
              httpOnly: true,
              secure: false,
              sameSite: "lax",
            });
          }
        );
      }

      // We need to reset the mongo database before each test
      cy.request(`${dbResetUrl}`);
      cy.wait(500);
    });

    it("renders on unexpected error on home screen", () => {
      cy.visit("/");
      cy.wait("@devices-list");
      cy.contains(500).should("be.visible");
      cy.contains("dummy server error").should("be.visible");
      cy.contains("button", /back/i).click();
    });

    it("renders on unexpected error on devices screen", () => {
      cy.visit("/devices");
      cy.wait("@devices-list");
      cy.contains(500).should("be.visible");
      cy.contains("dummy server error").should("be.visible");
      cy.contains("button", /back/i).click();
    });

    it("renders on unexpected error on device-detail screen", () => {
      cy.visit("/devices/loke");
      cy.wait("@loke-device");
      cy.wait(100);
      cy.contains(500).should("be.visible");
      cy.contains("dummy server error").should("be.visible");
      cy.contains("button", /back/i).click();
    });
  });
});
