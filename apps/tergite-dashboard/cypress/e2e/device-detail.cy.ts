/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import deviceList from "../fixtures/device-list.json";
import medianCalibrations from "../fixtures/median-calibrations.json";
// import bookingsFixture from "../fixtures/bookings.json";
import { generateJwt, getUsername } from "../../api/utils";
import { type Device, type User } from "../../types";

const users = [...userList] as User[];
const devices = deviceList.slice(0, 3) as Device[];
const calibrationProperties: { [k: string]: RegExp } = {
  t1_decoherence: /t1 decoherence/i,
  t2_decoherence: /t2 decoherence/i,
  anharmonicity: /anharmonicity/i,
  frequency: /frequency/i,
  readout_assignment_error: /readout error/i,
};
const medianCalibrationsDataMap: {
  [k: string]: { t1: string; t2: string; readout_error: string };
} = { ...medianCalibrations };

users.forEach((user) => {
  devices.forEach((device) => {
    const calibrationMedians = medianCalibrationsDataMap[device.id];
    const username = getUsername(user);
    let testThreshold: number;
    let platform: string;

    describe(`${device.name} device detail  for ${username}`, () => {
      beforeEach(() => {
        const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
        const dbResetUrl = Cypress.env("DB_RESET_URL");
        const domain = Cypress.env("VITE_COOKIE_DOMAIN");
        const cookieName = Cypress.env("VITE_COOKIE_NAME");
        const secret = Cypress.env("JWT_SECRET");
        const audience = Cypress.env("AUTH_AUDIENCE");
        platform = Cypress.env("PLATFORM");
        testThreshold = parseFloat(Cypress.env("TEST_THRESHOLD") || "0.3");
        cy.log(`test threshold: ${testThreshold}`);
        const cookieExpiry = Math.round(
          (new Date().getTime() + 800_000) / 1000
        );

        cy.intercept("GET", `${apiBaseUrl}/devices/${device.name}`).as(
          "devices-detail"
        );
        cy.intercept("GET", `${apiBaseUrl}/calibrations/${device.name}`).as(
          "calibrations-detail"
        );
        cy.intercept("GET", `${apiBaseUrl}/me/projects/?is_active=true`).as(
          "my-project-list"
        );

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

        cy.visit(`/devices/${device.name}`);
        cy.wait("@devices-detail");
        cy.wait("@calibrations-detail");
      });

      it("renders the summary of the device", () => {
        cy.viewport(1080, 750);
        cy.get("#device-summary").within(() => {
          // the header
          cy.contains(".grid", device.name).within(() => {
            cy.contains(device.name).should("be.visible");
            cy.contains(new RegExp(`version ${device.version}`, "i")).should(
              "be.visible"
            );
          });

          // the details body
          const statusRegex = device.is_online ? /online/i : /offline/i;
          const deviceTypeRegex = device.is_simulator
            ? /simulator/i
            : /physical/i;
          cy.contains(".grid", /details/i).within(() => {
            cy.contains("li", /status/i).within(() => {
              cy.contains(statusRegex).should("be.visible");
            });
            cy.contains("li", /basis gates/i).within(() => {
              cy.contains(device.basis_gates.join(", ")).should("be.visible");
            });
            cy.contains("li", /type/i).within(() => {
              cy.contains(deviceTypeRegex).should("be.visible");
            });
            cy.contains("li", /qubits/i).within(() => {
              cy.contains(`${device.number_of_qubits}`).should("be.visible");
            });
          });

          // the calibrations info
          cy.contains(".grid", /calibration information/i).within(() => {
            cy.contains("li", /median readout error/i).within(() => {
              cy.contains(calibrationMedians.readout_error).should(
                "be.visible"
              );
            });
            cy.contains("li", /median t1/i).within(() => {
              cy.contains(calibrationMedians.t1).should("be.visible");
            });
            cy.contains("li", /median t2/i).within(() => {
              cy.contains(calibrationMedians.t2).should("be.visible");
            });
          });

          // footer
          cy.contains("div", /last calibrated/i).within(() => {
            cy.contains(
              /last calibrated \d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i
            ).should("be.visible");
          });
        });
      });

      it("renders the map view", () => {
        cy.viewport(1280, 750);
        for (const property of Object.keys(calibrationProperties)) {
          cy.wrap(property).then((property) => {
            const regex = calibrationProperties[property];

            cy.contains("button", /map view/i).realClick();
            cy.contains("button", /property:/i)
              .realClick()
              .then(() => {
                cy.get("#prop-selector").within(() => {
                  cy.contains(regex).as("item-btn");
                  cy.get("@item-btn").realClick();
                });
              });

            cy.get("#map-view").compareSnapshot({
              name: `map-view-${platform}-for-${property}-of-${device.id}`,
              testThreshold: Math.max(testThreshold, 0.35),
              retryOptions: {
                limit: 2,
                delay: 500,
              },
            });
          });
        }
      });

      it("renders the graph view", () => {
        cy.viewport(1280, 750);
        for (const property of Object.keys(calibrationProperties)) {
          cy.wrap(property).then((property) => {
            const regex = calibrationProperties[property];

            cy.contains("button", /graph view/i).click();
            cy.contains("button", /property:/i).click();
            cy.get("#prop-selector").within(() => {
              cy.contains(regex).as("item-btn");
              cy.get("@item-btn").click();
            });
            cy.get("#graph-view").compareSnapshot({
              name: `graph-view-${platform}-for-${property}-of-${device.id}`,
              testThreshold,
              retryOptions: {
                limit: 2,
                delay: 500,
              },
            });
          });
        }
      });

      it("renders the table view", () => {
        cy.viewport(1280, 750);
        cy.contains("button", /table view/i).click();
        cy.get("#table-view").compareSnapshot({
          name: `table-${platform}-view-for-${device.id}`,
          testThreshold,
          retryOptions: {
            limit: 2,
            delay: 500,
          },
        });
      });

      describe(`bookings for the ${device.name}`, () => {
        // let expectedBookings: Booking[] = [];
        // const user_id = users[0].id;
        const username = users[0].email.split("@")[0];
        const currentUsername = user.email.split("@")[0];

        beforeEach(() => {
          const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
          const currentDateStr = Cypress.env("CURRENT_DATE");
          const currentDate = new Date(currentDateStr);

          // expectedBookings = bookingsFixture.map((v) => ({
          //   ...toBookingPayload(v, currentDate),
          //   user_id,
          //   username,
          //   total_duration: v.duration,
          //   id: "RANDOM_UUID",
          // }));

          cy.clock(currentDate, ["Date"]);
          cy.intercept(
            "GET",
            `${apiBaseUrl}/bookings/${device.name}/config`
          ).as("bookings-config");
          cy.intercept("GET", `${apiBaseUrl}/bookings/${device.name}?`).as(
            "bookings-list"
          );

          cy.viewport(1280, 750);
          cy.contains("button", /bookings/i).realClick();
          cy.wait("@bookings-list");
        });

        it("renders the calendar view", () => {
          cy.get("[data-cy-calendar-event]").first().scrollIntoView();
          cy.get("#calendar-view").compareSnapshot({
            name: `calendar-view-${platform}-of-${device.id}`,
            testThreshold: Math.max(testThreshold, 0.35),
            retryOptions: {
              limit: 2,
              delay: 500,
            },
          });
        });

        it("renders the basic details of a booking", () => {
          cy.get("[data-cy-calendar-event]").each((el) => {
            cy.wrap(el)
              .scrollIntoView()
              .within(() => {
                cy.contains(username).should("exist");
                // for short bookings, the text gets cut off
                cy.contains(".fc-event-time", /\d\d?:\d\d - \d\d?:\d\d/).should(
                  "be.visible"
                );
              });
          });
        });

        it("renders the details of a booking on tapping the booking in the calendar", () => {
          cy.get("[data-cy-calendar-event]").each((el, idx) => {
            cy.contains("#calendar-view .flex", "Bookings data").realClick();
            cy.get("[data-cy-event-details]").should("not.exist");

            cy.wrap(el)
              .scrollIntoView()
              .contains(".fc-event-main-frame", username)
              .realClick();
            cy.get("[data-cy-event-details]").within(() => {
              cy.contains(username).should("be.visible");
              cy.contains(/\d?\d:\d\d - \d?\d:\d\d/).should("be.visible");
              cy.contains("div", /device/i).within(() => {
                cy.contains(device.name).should("be.visible");
              });
              cy.contains("div", /duration/i).within(() => {
                cy.contains(
                  /(\+?\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+/i
                ).should("be.visible");
              });
              // The first two events are in the past.
              if (idx > 1 && username === currentUsername) {
                cy.contains("button", /edit/i).should("be.visible");
              } else {
                cy.contains("button", /edit/i).should("not.exist");
              }
            });
          });
        });
      });

      // creating new booking by tapping any empty cell in the calendar
      // cancelling creating new booking by tapping any empty cell in the calendar
      // editing by tapping edit button of the booking popup
      // cancelling editing by tapping edit button of the booking popup
      // editing a booking by drag and drop
    });
  });
});
