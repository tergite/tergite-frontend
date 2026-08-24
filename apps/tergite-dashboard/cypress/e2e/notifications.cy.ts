/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import notificationList from "../fixtures/notifications.json";
import projectList from "../fixtures/projects.json";
import userList from "../fixtures/users.json";
import { generateJwt } from "../../api/utils";
import { type Project, type User } from "../../types";

// the fixture carries the stored shape, which includes the recipient; the API only
// ever returns the caller's own notifications, so NotificationRead has no user_id
interface StoredNotification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  read_at: string | null;
  action: { kind: string; request_id: string } | null;
}

const users = [...userList] as User[];
const projects = [...projectList] as Project[];
const notifications = [...notificationList] as StoredNotification[];

// only the users the fixture actually gives notifications to are worth iterating
const recipients = users.filter((user) =>
  notifications.some((v) => v.user_id === user.id),
);

function login(user: User, path: string) {
  const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
  const dbResetUrl = Cypress.env("DB_RESET_URL");
  const domain = Cypress.env("VITE_COOKIE_DOMAIN");
  const cookieName = Cypress.env("VITE_COOKIE_NAME");
  const secret = Cypress.env("JWT_SECRET");
  const audience = Cypress.env("AUTH_AUDIENCE");
  const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

  cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");
  cy.intercept("GET", `${apiBaseUrl}/me`).as("my-user-info");
  cy.intercept("GET", `${apiBaseUrl}/me/projects/?*`).as("my-project-list");
  cy.intercept("GET", `${apiBaseUrl}/me/notifications/*`).as("my-notifications");
  cy.intercept("GET", `${apiBaseUrl}/counts/notifications*`).as(
    "notification-count",
  );
  cy.intercept("POST", `${apiBaseUrl}/me/requests/`).as("request-create");
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

  cy.request(`${dbResetUrl}`);
  cy.wait(500);
  cy.visit(path);
  cy.wait("@my-user-info");
}

recipients.forEach((user) => {
  const username = user.email.split("@")[0];
  const mine = notifications.filter((v) => v.user_id === user.id);
  const unread = mine.filter((v) => !v.read_at);
  const actionable = mine.filter((v) => !!v.action);

  describe(`notifications for ${username}`, () => {
    beforeEach(() => {
      login(user, "/");
      cy.wait("@my-notifications");
    });

    it("shows the unread count on the bell", () => {
      if (unread.length > 0) {
        cy.get("[data-cy-unread-count]").should("contain.text", unread.length);
      } else {
        cy.get("[data-cy-unread-count]").should("not.exist");
      }
    });

    it("lists only this user's notifications", () => {
      cy.get("[data-cy-notifications-bell]").click();
      cy.get("#notifications-panel").within(() => {
        cy.get("li").should("have.length", mine.length);
        for (const item of mine) {
          cy.contains("li", item.title).should("be.visible");
        }
      });
    });

    it("shows approve and reject only where the recipient can act", () => {
      cy.get("[data-cy-notifications-bell]").click();
      cy.get("#notifications-panel").within(() => {
        for (const item of mine) {
          cy.contains("li", item.title).within(() => {
            const assertion = item.action ? "be.visible" : "not.exist";
            cy.contains("button", /approve/i).should(assertion);
            cy.contains("button", /reject/i).should(assertion);
          });
        }
      });
    });

    unread.length > 0 &&
      it("marks one notification read", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.get("#notifications-panel [data-cy-mark-read]").first().click();
        cy.wait("@my-notifications");

        cy.get("#notifications-panel [data-cy-unread='true']").should(
          "have.length",
          unread.length - 1,
        );
      });

    unread.length > 0 &&
      it("marks every notification read", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.get("[data-cy-mark-all-read]").click();
        cy.wait("@my-notifications");

        cy.get("[data-cy-unread-count]").should("not.exist");
      });

    actionable.length > 0 &&
      it("approving from the bell clears the actionable notification", () => {
        cy.get("[data-cy-notifications-bell]").click();
        cy.contains("#notifications-panel li", actionable[0].title).within(
          () => {
            cy.contains("button", /approve/i).click();
          },
        );

        cy.wait("@request-react").its("response.statusCode").should("eq", 200);
      });
  });
});

// pick a user who both belongs to a project and is absent from another, so every
// request-access branch is reachable without adding projects to the shared fixture
const requester = users.find(
  (user) =>
    projects.some((v) => v.user_ids.includes(user.id)) &&
    projects.some((v) => !v.user_ids.includes(user.id) && v.admin_id !== user.id),
) as User;

describe("requesting project access", () => {
  const foreign = projects.find(
    (v) => !v.user_ids.includes(requester.id) && v.admin_id !== requester.id,
  ) as Project;
  const own = projects.find((v) =>
    v.user_ids.includes(requester.id),
  ) as Project;

  beforeEach(() => {
    login(requester, "/projects");
    cy.wait("@my-project-list");
  });

  it("submits a request for a project the user is not on", () => {
    cy.get("[data-cy-request-access]").click();
    cy.get("#request-access-dialog").within(() => {
      cy.get("#project_ext_id").type(foreign.ext_id);
      cy.get("#reason").type("joining this collaboration");
      cy.contains("button", /submit/i).click();
    });

    cy.wait("@request-create").its("response.statusCode").should("eq", 201);
    cy.get("#request-access-dialog").should("not.exist");
    cy.contains(/access requested/i).should("be.visible");
  });

  it("reports an unknown project id on the field rather than as a toast", () => {
    cy.get("[data-cy-request-access]").click();
    cy.get("#request-access-dialog").within(() => {
      cy.get("#project_ext_id").type("no-such-project-anywhere");
      cy.get("#reason").type("please");
      cy.contains("button", /submit/i).click();

      cy.contains(/no project with ID/i).should("be.visible");
    });
  });

  it("refuses a project the user already belongs to", () => {
    cy.get("[data-cy-request-access]").click();
    cy.get("#request-access-dialog").within(() => {
      cy.get("#project_ext_id").type(own.ext_id);
      cy.get("#reason").type("again please");
      cy.contains("button", /submit/i).click();

      cy.contains(/already a member/i).should("be.visible");
    });
  });

  it("refuses a second pending request for the same project", () => {
    for (const attempt of [1, 2]) {
      cy.get("[data-cy-request-access]").click();
      cy.get("#request-access-dialog").within(() => {
        cy.get("#project_ext_id").type(foreign.ext_id);
        cy.get("#reason").type(`attempt ${attempt}`);
        cy.contains("button", /submit/i).click();

        if (attempt === 2) {
          cy.contains(/already pending/i).should("be.visible");
        }
      });
      if (attempt === 1) {
        cy.get("#request-access-dialog").should("not.exist");
      }
    }
  });
});
