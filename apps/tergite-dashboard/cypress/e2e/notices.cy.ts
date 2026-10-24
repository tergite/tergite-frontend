/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import noticeList from "../fixtures/notices.json";
import userList from "../fixtures/users.json";
import { generateJwt } from "../../dev/mock-api/utils";
import { type User } from "../../types";

// the fixture carries the stored shape, with relative offsets for the timestamps
interface StoredNotice {
  id: string;
  user_id: string | null;
  type: string;
  title: string;
  dismissed_by: string[];
  expires_at_offset_hours: number | null;
}

// one who can act on a notice, one with notices of their own, and one with broadcasts only
const users = ([...userList] as User[]).filter((v) =>
  ["jane.doe@example.com", "john.doe@example.com", "julie.doe@example.com"].includes(v.email)
);
const notices = [...noticeList] as StoredNotice[];

function login(user: User, path: string) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
  cy.intercept("GET", `${apiBaseUrl}/me/profile`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/me/notices/?*`).as("my-notices");
  cy.intercept("GET", `${apiBaseUrl}/counts/notices*`).as("notice-count");
  cy.intercept("POST", `${apiBaseUrl}/me/notices/*/dismiss`).as(
    "notice-dismiss",
  );
  cy.intercept("PUT", `${apiBaseUrl}/me/requests/*`).as("request-react");

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

  cy.resetDatabase();
  cy.visit(path);
  cy.wait("@my-user-info");
}

users.forEach((user) => {
  const username = user.email.split("@")[0];
  // the bell lists the unread notices only; expired ones no longer exist
  const unread = notices.filter(
    (v) =>
      (v.user_id === null || v.user_id === user.id) &&
      !v.dismissed_by.includes(user.id) &&
      (v.expires_at_offset_hours === null || v.expires_at_offset_hours >= 0),
  );
  // the prompts to decide a request are the only ones that can be acted on
  const actionable = unread.filter((v) => v.type.endsWith("-requested"));

  describe(`notices for ${username}`, () => {
    beforeEach(() => {
      login(user, "/");
      cy.wait("@my-notices");
    });

    it("shows the unread count on the bell", () => {
      cy.wait("@notice-count");
      if (unread.length > 0) {
        cy.get("[data-cy-unread-count]").should("contain.text", unread.length);
      } else {
        cy.get("[data-cy-unread-count]").should("not.exist");
      }
    });

    it("lists only this user's unread notices", () => {
      cy.get("[data-cy-notifications-bell]").click();
      cy.get("#notifications-panel").within(() => {
        cy.get("li").should("have.length", unread.length);
        for (const item of unread) {
          // the panel scrolls, so the later ones are out of sight until scrolled to
          cy.contains("li", item.title).scrollIntoView().should("be.visible");
        }
      });
    });

    it("shows approve and reject only where the recipient can act", () => {
      cy.get("[data-cy-notifications-bell]").click();
      cy.get("#notifications-panel").within(() => {
        for (const item of unread) {
          cy.contains("li", item.title).within(() => {
            const assertion =
              actionable.includes(item) ? "be.visible" : "not.exist";
            cy.contains("button", /approve/i).should(assertion);
            cy.contains("button", /reject/i).should(assertion);
          });
        }
      });
    });

    unread.length > 0 &&
      it("marks one notice read", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.get("#notifications-panel [data-cy-mark-read]").first().click();
        cy.wait("@my-notices");

        cy.get("#notifications-panel li").should(
          "have.length",
          unread.length - 1,
        );
      });

    unread.length > 0 &&
      it("marks every notice read", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.get("[data-cy-mark-all-read]").click();
        cy.wait("@my-notices");

        cy.get("[data-cy-unread-count]").should("not.exist");
      });

    actionable.length > 0 &&
      it("approving from the bell clears the actionable notice", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.contains("#notifications-panel li", actionable[0].title).within(
          () => {
            cy.contains("button", /approve/i).click();
          },
        );

        cy.wait("@request-react").its("response.statusCode").should("eq", 200);
      });

    // every user has the broadcasts ntc_007 and ntc_009 in force
    it("shows a notice in force in the top banner", () => {
      cy.get('[data-testid="top-banner"]').within(() => {
        cy.get('[aria-label="Dismiss notice"]').should("be.visible");
        cy.contains(/\b(info|warning|critical)\b/i).should("be.visible");
      });
    });

    it("takes a notice dismissed from the top banner off the bell", () => {
      cy.get(
        '[data-testid="top-banner"] [aria-label="Dismiss notice"]',
      ).click();
      cy.wait("@notice-dismiss");

      cy.get("[data-cy-unread-count]").should(
        "contain.text",
        unread.length - 1,
      );
    });
  });
});
