/// <reference types="cypress" />

import userList from "../fixtures/users.json";
import deviceList from "../fixtures/device-list.json";
import { generateJwt, getUsername } from "../../dev/mock-api/utils";
import { type Device, type User } from "../../types";

const users = [...userList] as User[];
const devices = [...deviceList] as Device[];

users.forEach((user) => {
  const username = getUsername(user);

  describe(`devices list page for ${username}`, () => {
    let apiBaseUrl: string = "";
    beforeEach(() => {
      apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

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
    });

    it("renders the summaries of all devices", () => {
      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("devices-list");

      cy.visit("/devices");
      cy.wait("@devices-list");

      cy.viewport(1080, 750);
      for (const device of devices) {
        cy.wrap(device).then((device) => {
          cy.contains(".bg-card", device.name).within(() => {
            const statusRegex = device.is_online ? /online/i : /offline/i;
            const lastOnlineRegex = device.last_online
              ? /\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i
              : /N\/A/i;

            cy.contains(device.name).should("be.visible");
            cy.contains(statusRegex).should("be.visible");
            cy.contains("div", /last seen/i).within(() => {
              cy.contains(lastOnlineRegex).should("be.visible");
            });
            cy.contains("div", /qubits/i).within(() => {
              cy.contains(`${device.number_of_qubits}`).should("be.visible");
            });
          });
        });
      }
    });

    it("renders no devices found if no devices are returned", () => {
      cy.intercept("GET", `${apiBaseUrl}/devices/*`, {
        body: { data: [], limit: null, skip: 0 },
      }).as("devices-list");

      cy.visit("/devices");
      cy.wait("@devices-list");

      cy.viewport(1080, 750);
      cy.contains("main", /no devices found/i).should("exist");
    });
  });
});
