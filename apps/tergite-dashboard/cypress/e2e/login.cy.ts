/// <reference types="cypress" />

import userList from "../fixtures/users.json";
import authProviders from "../fixtures/auth-providers.json";
import { User } from "../../types";
import { decodeJwt } from "jose";
import { generateJwt } from "../../dev/mock-api/utils";

const invalidFormatEmailAddresses = [
  "john",
  "1",
  "john.com",
  "http://example.com",
];

// an email domain with a provider, and one without
const users = ([...userList] as User[]).filter((v) =>
  ["jane.doe@example.com", "wrong.domain@domain.com"].includes(v.email)
);

users.forEach((user) => {
  const [username, emailDomain] = user.email.split("@");
  const availableAuthProviders = authProviders.filter(
    (v) => v.email_domain === emailDomain
  );
  const isDomainSupported = availableAuthProviders.length > 0;

  describe(`login page for authenticated user '${username}'`, () => {
    const dashboardUrl = Cypress.config("baseUrl");
    const isFullE2E = dashboardUrl?.startsWith("http://127.0.0.1:3000");

    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const userIdCookieName = Cypress.env("USER_ID_COOKIE_NAME");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/*`).as("my-project-list");
      cy.intercept("GET", `${apiBaseUrl}/me/jobs/*`).as("my-jobs-list");
      if (isFullE2E) {
        const openidAuthUrl = Cypress.env("OPENID_AUTH_URL");
        // Just some work arounds to avoid having to set up a real OpenID Connect server
        // - This means that the actual app does not work exactly like this, but
        //   the testing involved here is sufficient.
        cy.intercept("GET", "/?set-cookie=true", async (req) => {
          const token = await generateJwt(user, cookieExpiry, {
            secret,
            audience,
          });
          const cookie = `${cookieName}=${token}; Domain=${domain}; Secure; HttpOnly; SameSite=Lax; Path=/; Expires=${cookieExpiry}`;
          req.continue((res) => {
            res.headers["Set-Cookie"] = cookie;
          });
        }).as("cookie-setter");

        cy.intercept("GET", `${openidAuthUrl}*`, async (req) => {
          const stateObj = decodeJwt(`${req.query.state}`);
          req.redirect(`${stateObj.next}?set-cookie=true`);
        }).as("auth0-authorize");
      }

      cy.setCookie(userIdCookieName, user.id, {
        domain,
        httpOnly: true,
        secure: false,
        sameSite: "lax",
      });

      // We need to reset the mongo database before each test
      cy.request(`${dbResetUrl}`);

      cy.visit("/");
      cy.wait("@devices-list");

      cy.get("input[name=email]").as("emailInput");
      cy.get("button[type=submit]").contains(/next/i).as("nextBtn");
    });

    it("renders correctly", () => {
      cy.get("[data-cy-logo]").should("contain.text", "WACQT");
      cy.get("[data-cy-logo]").should(
        "contain.text",
        "Wallenberg Centre for Quantum Technology"
      );

      cy.get("@emailInput")
        .should("have.attr", "placeholder")
        .and("match", /email address:/i);

      cy.get("@nextBtn").should("be.visible");
    });

    !isDomainSupported &&
      it(`renders 'unauthorized' error message for '${user.email}'`, () => {
        cy.get("p.text-destructive").should("not.exist");

        cy.get("@emailInput").clear();
        cy.get("@emailInput").type(user.email);
        cy.get("@nextBtn").click();

        cy.get("p.text-destructive")
          .contains(/not found/i)
          .should("be.visible");
      });

    isDomainSupported &&
      it(`redirects to the home page of the dashboard`, () => {
        cy.get("@emailInput").clear();
        cy.get("@emailInput").type(user.email);
        cy.get("@nextBtn").realClick();

        cy.get("[data-cy-login-link]").first().realClick();
        let finalUrl = dashboardUrl;
        if (isFullE2E) {
          cy.wait("@auth0-authorize");
          finalUrl = `${dashboardUrl}?set-cookie=true`;
        }

        cy.wait("@my-jobs-list");

        cy.url().should("equal", finalUrl);
        cy.get("nav a")
          .contains(/dashboard/i)
          .should("be.visible");
      });
  });

  describe(`login page for unauthenticated user '${username}'`, () => {
    const dashboardUrl = Cypress.config("baseUrl");

    let apiBaseUrl: string;
    beforeEach(() => {
      apiBaseUrl = Cypress.env("VITE_API_BASE_URL");

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/?is_active=true`).as(
        "my-project-list"
      );
      cy.intercept("GET", `${apiBaseUrl}/me/jobs/*`).as("my-jobs-list");
      cy.intercept(
        "GET",
        `${apiBaseUrl}/auth/providers/?email_domain=${emailDomain}`
      ).as("auth-providers");

      cy.visit("/");
      cy.wait("@devices-list");

      cy.get("input[name=email]").as("emailInput");
      cy.get("button[type=submit]").contains(/next/i).as("nextBtn");
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

    isDomainSupported &&
      it(`redirects to the home page of the dashboard`, () => {
        cy.get("@emailInput").clear();
        cy.get("@emailInput").type(user.email);
        cy.get("@nextBtn").click();

        cy.wait("@auth-providers");

        for (const provider of availableAuthProviders) {
          cy.wrap(provider).then((provider) => {
            cy.contains(
              "a",
              new RegExp(`login with ${provider.name}`, "i")
            ).should(
              "have.attr",
              "href",
              `${apiBaseUrl}/auth/${
                provider.name
              }/auto-authorize?next=${dashboardUrl?.slice(0, -1)}`
            );
          });
        }
      });
  });
});

invalidFormatEmailAddresses.forEach((email) =>
  describe(`login with invalid email ${email}`, () => {
    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/*`).as("my-project-list");

      cy.visit("/");
      cy.wait("@devices-list");
    });

    it(`renders error message`, () => {
      cy.get("p.text-destructive").should("not.exist");

      cy.get("input[name=email]").type(email);
      cy.get("button[type=submit]").contains(/next/i).click();

      cy.get("p.text-destructive")
        .contains(/invalid email; expected xxx@bxxxx.xxx/i)
        .should("be.visible");
    });
  })
);
