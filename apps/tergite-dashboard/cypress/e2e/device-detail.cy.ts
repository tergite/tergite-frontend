/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import deviceList from "../fixtures/device-list.json";
import medianCalibrations from "../fixtures/median-calibrations.json";
import bookingsConfigList from "../fixtures/bookings-configs.json";
import bookingsFixture from "../fixtures/bookings.json";
import { BookingsConfigInDb, generateJwt, getUsername } from "../../api/utils";
import { Booking, type Device, type User } from "../../types";

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
const bookingsConfigs = [...bookingsConfigList] as BookingsConfigInDb[];
const bookingsConfigsMap = Object.fromEntries(
  bookingsConfigs.map((v) => [v.id, v])
);
const futureBookingsFixture = bookingsFixture.filter((v) => v.starts_in > 1500);

users.slice(0, 4).forEach((user) => {
  devices.forEach((device) => {
    const calibrationMedians = medianCalibrationsDataMap[device.id];
    const bookingConfigs = bookingsConfigsMap[device.name];
    const username = getUsername(user);
    let testThreshold: number;
    let platform: string;
    let apiBaseUrl: string;
    let dbResetUrl: string;
    let currentDateStr: string;
    let currentDate: Date;

    describe(`${device.name} device detail  for ${username}`, () => {
      beforeEach(() => {
        apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
        dbResetUrl = Cypress.env("DB_RESET_URL");
        const domain = Cypress.env("VITE_COOKIE_DOMAIN");
        const cookieName = Cypress.env("VITE_COOKIE_NAME");
        const secret = Cypress.env("JWT_SECRET");
        const audience = Cypress.env("AUTH_AUDIENCE");
        currentDateStr = Cypress.env("CURRENT_DATE");
        currentDate = new Date(currentDateStr);
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
        let testTimestamp: Date;
        let currentLocaleDateStr: string;
        let testLocaleDateStr: string;
        let testISODateStr: string;
        let testISOTimeStr: string;
        let currentISODateStr: string;
        let currentISOTimeStr: string;
        const username = users[0].email.split("@")[0];
        const currentUsername = user.email.split("@")[0];
        const defaultDuration = convertSecToDuration(
          bookingConfigs.min_time_slot_length
        );
        const defaultDurationStr = convertSecToDurationStr(
          bookingConfigs.min_time_slot_length
        );
        const invalidDurations = [
          bookingConfigs.min_time_slot_length - 60,
          bookingConfigs.max_time_slot_length + 60,
        ];
        let expectedBookings: Booking[] = [];

        beforeEach(() => {
          const timezoneOffset = new Date().getTimezoneOffset() * 60;
          testTimestamp = addSeconds(currentDate, 4 * 3_600 - timezoneOffset);
          testLocaleDateStr = toLocaleDateStr(testTimestamp);
          currentLocaleDateStr = toLocaleDateStr(currentDate);
          testISODateStr = toISODateStr(testTimestamp);
          testISOTimeStr = toISOTimeStr(testTimestamp);
          currentISODateStr = toISODateStr(currentDate);
          currentISOTimeStr = toISOTimeStr(currentDate);

          cy.clock(currentDate, ["Date"]);
          cy.request(`${apiBaseUrl}/bookings/${device.name}`).then((resp) => {
            expectedBookings = resp.body.data;
          });
          cy.intercept(
            "GET",
            `${apiBaseUrl}/bookings/${device.name}/config`
          ).as("bookings-config");
          cy.intercept("GET", `${apiBaseUrl}/bookings/${device.name}?`).as(
            "bookings-list"
          );

          // We need to reset the mongo database before each test
          cy.request(`${dbResetUrl}`);
          cy.wait(500);

          cy.viewport(1280, 750);
          cy.contains("button", /bookings/i).realClick();
          cy.wait("@bookings-list");
          cy.wait(100);
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
                cy.contains("button.border.border-input", /edit/i).should(
                  "be.visible"
                );
                cy.contains("button.bg-destructive", /discard/i).should(
                  "be.visible"
                );
              } else {
                cy.contains("button", /edit/i).should("not.exist");
                cy.contains("button", /discard/i).should("not.exist");
              }
            });
          });
        });

        it("tapping an empty cell in the calendar opens a form for creating a new booking with that cell's start date", () => {
          cy.viewport(1440, 1080);
          const startTimeStr = get12HourTimeString(testTimestamp);
          const endTime = addSeconds(
            testTimestamp,
            bookingConfigs.min_time_slot_length
          );
          const endTimeStr = get12HourTimeString(endTime);

          cy.get("#booking-form-dialog").should("not.exist");
          cy.contains(
            ".fc-event-time",
            `${startTimeStr} - ${endTimeStr}`
          ).should("not.exist");

          cy.get("#calendar-view")
            .clickCalendarCell(testISODateStr, testISOTimeStr)
            .then(() => {
              cy.get("#booking-form-dialog").should("exist");
              cy.get("#booking-form-dialog")
                .within(() => {
                  cy.contains("h2", /create new booking/i).should("be.visible");
                  cy.contains(
                    "button#datetime-input",
                    new RegExp(`${testLocaleDateStr}, ${testISOTimeStr}`, "i")
                  ).should("be.visible");
                  cy.get("input#duration[type='hidden']").should(
                    "have.value",
                    defaultDurationStr
                  );
                  cy.get("input#duration-hours[type='number']").should(
                    "have.value",
                    `${defaultDuration.hours}`
                  );
                  cy.get("input#duration-minutes[type='number']").should(
                    "have.value",
                    `${defaultDuration.minutes}`
                  );
                  cy.get("input#duration-seconds[type='number']").should(
                    "have.value",
                    `${defaultDuration.seconds}`
                  );

                  // Creates a new booking
                  cy.contains("button", /save/i).click();
                })
                .then(() => {
                  cy.contains(
                    ".fc-event-time",
                    `${startTimeStr} - ${endTimeStr}`
                  ).should("be.visible");
                });
            });
        });

        it("Clicking cancel in the booking creation form cancels the event creation", () => {
          const startTimeStr = get12HourTimeString(testTimestamp);
          const endTime = addSeconds(
            testTimestamp,
            bookingConfigs.min_time_slot_length
          );
          const endTimeStr = get12HourTimeString(endTime);

          cy.get("#booking-form-dialog").should("not.exist");
          cy.contains(
            ".fc-event-time",
            `${startTimeStr} - ${endTimeStr}`
          ).should("not.exist");

          cy.get("#calendar-view")
            .clickCalendarCell(testISODateStr, testISOTimeStr)
            .then(() => {
              cy.contains("#booking-form-dialog button", /cancel/i)
                .click()
                .then(() => {
                  cy.contains(
                    ".fc-event-time",
                    `${startTimeStr} - ${endTimeStr}`
                  ).should("not.exist");
                });
            });
        });

        it("editing the default values in the creation form allows creation of booking with those values", () => {
          cy.viewport(1440, 1080);
          const startTimeStr = get12HourTimeString(testTimestamp);
          const duration = Math.min(
            bookingConfigs.max_time_slot_length,
            bookingConfigs.min_time_slot_length + 900
          );
          const durationObj = convertSecToDuration(duration);
          const endTime = addSeconds(testTimestamp, duration);
          const endTimeStr = get12HourTimeString(endTime);

          cy.get("#booking-form-dialog").should("not.exist");
          cy.contains(
            ".fc-event-time",
            `${startTimeStr} - ${endTimeStr}`
          ).should("not.exist");

          cy.get("#calendar-view")
            .clickCalendarCell(currentISODateStr, currentISOTimeStr)
            .then(() => {
              cy.get("#booking-form-dialog")
                .within(() => {
                  // {selectall} ensures the existing text is replaced by the new value
                  cy.get("input#duration-hours[type='number']").type(
                    `{selectall}${durationObj.hours}`
                  );
                  cy.get("input#duration-minutes[type='number']").type(
                    `{selectall}${durationObj.minutes}`
                  );
                  cy.get("input#duration-seconds[type='number']").type(
                    `{selectall}${durationObj.seconds}`
                  );

                  cy.contains(
                    "button#datetime-input",
                    new RegExp(
                      `${currentLocaleDateStr}, ${currentISOTimeStr}`,
                      "i"
                    )
                  ).click();

                  cy.get(
                    "[data-radix-popper-content-wrapper] input[type='time']"
                  ).type(testISOTimeStr);

                  // save
                  cy.contains("button", /save/i).click();
                })
                .then(() => {
                  cy.contains(
                    ".fc-event-time",
                    `${startTimeStr} - ${endTimeStr}`
                  ).should("be.visible");
                });
            });
        });

        invalidDurations.forEach((duration) => {
          const titlePatch =
            duration > bookingConfigs.max_time_slot_length
              ? "greater than max"
              : "less than min";

          it(`entering a duration ${titlePatch} duration raises errors in the creation form`, () => {
            cy.viewport(1440, 1080);
            const startTimeStr = get12HourTimeString(testTimestamp);
            const durationObj = convertSecToDuration(duration);
            const endTime = addSeconds(testTimestamp, duration);
            const endTimeStr = get12HourTimeString(endTime);
            const minDurationStr = convertSecToDurationStr(
              bookingConfigs.min_time_slot_length
            );
            const maxDurationStr = convertSecToDurationStr(
              bookingConfigs.max_time_slot_length
            );
            const errMsg = `duration must be between ${minDurationStr} and ${maxDurationStr}`;

            cy.get("#booking-form-dialog").should("not.exist");
            cy.contains(
              ".fc-event-time",
              `${startTimeStr} - ${endTimeStr}`
            ).should("not.exist");

            cy.get("#calendar-view")
              .clickCalendarCell(currentISODateStr, currentISOTimeStr)
              .then(() => {
                cy.get("#booking-form-dialog")
                  .within(() => {
                    // {selectall} ensures that the existing value is replaced by the new value
                    //  otherwise clearing it would make the browser automatically add a '0'
                    // which would be appended to the new value that is typed in
                    cy.get("input#duration-hours[type='number']").type(
                      `{selectall}${durationObj.hours}`
                    );
                    cy.get("input#duration-minutes[type='number']").type(
                      `{selectall}${durationObj.minutes}`
                    );
                    cy.get("input#duration-seconds[type='number']").type(
                      `{selectall}${durationObj.seconds}`
                    );

                    cy.contains(
                      "button#datetime-input",
                      new RegExp(
                        `${currentLocaleDateStr}, ${currentISOTimeStr}`,
                        "i"
                      )
                    ).click();

                    cy.get(
                      "[data-radix-popper-content-wrapper] input[type='time']"
                    ).type(testISOTimeStr);

                    cy.contains("div.space-y-2", /duration/i).within(() => {
                      cy.contains(
                        "p.text-destructive",
                        new RegExp(errMsg)
                      ).should("not.exist");
                    });

                    // save
                    cy.contains("button", /save/i)
                      .click()
                      .then(() => {
                        cy.contains("div.space-y-2", /duration/i).within(() => {
                          cy.contains(
                            "p.text-destructive",
                            new RegExp(errMsg)
                          ).should("be.visible");
                        });
                      });
                  })
                  .then(() => {
                    cy.contains(
                      ".fc-event-time",
                      `${startTimeStr} - ${endTimeStr}`
                    ).should("not.exist");
                  });
              });
          });
        });

        it(`entering a start date that is in the past raises errors in the creation form`, () => {
          cy.viewport(1440, 1080);
          const startTimestamp = addSeconds(currentDate, -900);
          const startISOTimeStr = startTimestamp.toLocaleTimeString("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
          });
          const startTimeStr = get12HourTimeString(startTimestamp);
          const duration = Math.min(
            bookingConfigs.max_time_slot_length,
            bookingConfigs.min_time_slot_length + 900
          );
          const durationObj = convertSecToDuration(duration);
          const endTime = addSeconds(testTimestamp, duration);
          const endTimeStr = get12HourTimeString(endTime);

          const errMsg = `date must be in future`;

          cy.get("#booking-form-dialog").should("not.exist");
          cy.contains(
            ".fc-event-time",
            `${startTimeStr} - ${endTimeStr}`
          ).should("not.exist");

          cy.get("#calendar-view")
            .clickCalendarCell(currentISODateStr, currentISOTimeStr)
            .then(() => {
              cy.get("#booking-form-dialog")
                .within(() => {
                  cy.get("input#duration-hours[type='number']").type(
                    `{selectall}${durationObj.hours}`
                  );
                  cy.get("input#duration-minutes[type='number']").type(
                    `{selectall}${durationObj.minutes}`
                  );
                  cy.get("input#duration-seconds[type='number']").type(
                    `{selectall}${durationObj.seconds}`
                  );

                  cy.contains(
                    "button#datetime-input",
                    new RegExp(
                      `${currentLocaleDateStr}, ${currentISOTimeStr}`,
                      "i"
                    )
                  ).click();

                  cy.get(
                    "[data-radix-popper-content-wrapper] input[type='time']"
                  ).type(startISOTimeStr);

                  cy.contains("div.space-y-2", /start/i).within(() => {
                    cy.contains(
                      "p.text-destructive",
                      new RegExp(errMsg)
                    ).should("not.exist");
                  });

                  // save
                  cy.contains("button", /save/i)
                    .click()
                    .then(() => {
                      cy.contains("div.space-y-2", /start/i).within(() => {
                        cy.contains(
                          "p.text-destructive",
                          new RegExp(errMsg)
                        ).should("be.visible");
                      });
                    });
                })
                .then(() => {
                  cy.contains(
                    ".fc-event-time",
                    `${startTimeStr} - ${endTimeStr}`
                  ).should("not.exist");
                });
            });
        });

        futureBookingsFixture.slice(0, 3).forEach((bookingInfo) => {
          if (username === currentUsername) {
            it(`tapping the edit button on the booking that starts in ${bookingInfo.starts_in} seconds, opens edit form`, () => {
              cy.viewport(1440, 1080);
              const startTimeStr = get12HourTimeString(testTimestamp);
              const duration = Math.min(
                bookingConfigs.max_time_slot_length,
                bookingConfigs.min_time_slot_length + 900
              );
              const durationObj = convertSecToDuration(duration);
              const endTime = addSeconds(testTimestamp, duration);
              const endTimeStr = get12HourTimeString(endTime);
              const booking = findBooking(
                expectedBookings,
                bookingInfo,
                currentDate
              );

              const originalStartUtc = new Date(booking.start_utc);
              const oldStartTimeStr = get12HourTimeString(originalStartUtc);
              const oldEndTimeStr = get12HourTimeString(
                new Date(booking.end_utc)
              );

              const newTimeRangeStr = `${startTimeStr} - ${endTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;

              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;

              cy.get(eventElemSelector).as("eventElem");
              cy.contains("#calendar-view .flex", "Bookings data").realClick();
              cy.get("[data-cy-event-details]").should("not.exist");

              cy.get("@eventElem").scrollIntoView();
              cy.contains(eventElemSelector, oldTimeRangeStr).should(
                "be.visible"
              );
              cy.contains(".fc-event-main-frame", newTimeRangeStr).should(
                "not.exist"
              );
              cy.get("@eventElem")
                .contains(".fc-event-main-frame", username)
                .click();

              cy.get("#booking-form-dialog").should("not.exist");

              cy.contains("[data-cy-event-details] button", /edit/i)
                .click()
                .then(() => {
                  cy.get("#booking-form-dialog").should("be.visible");
                  cy.get("[data-cy-event-details]").should("not.exist");

                  cy.get("#booking-form-dialog")
                    .within(() => {
                      cy.get("input#duration-hours[type='number']").type(
                        `{selectall}${durationObj.hours}`
                      );
                      cy.get("input#duration-minutes[type='number']").type(
                        `{selectall}${durationObj.minutes}`
                      );
                      cy.get("input#duration-seconds[type='number']").type(
                        `{selectall}${durationObj.seconds}`
                      );

                      cy.get("button#datetime-input").click();
                      cy.get(
                        "[data-radix-popper-content-wrapper] input[type='time']"
                      ).type(testISOTimeStr);

                      // save
                      cy.contains("button", /save/i).click();
                    })
                    .then(() => {
                      cy.wait("@bookings-list");
                      cy.contains(eventElemSelector, oldTimeRangeStr).should(
                        "not.exist"
                      );
                      cy.contains(".fc-event-main-frame", newTimeRangeStr)
                        .scrollIntoView()
                        .should("be.visible");
                    });
                });
            });

            it(`tapping the cancel button when editing the booking starting in ${bookingInfo.starts_in} seconds, cancels everything`, () => {
              cy.viewport(1440, 1080);
              const startTimeStr = get12HourTimeString(testTimestamp);
              const duration = Math.min(
                bookingConfigs.max_time_slot_length,
                bookingConfigs.min_time_slot_length + 900
              );
              const endTime = addSeconds(testTimestamp, duration);
              const endTimeStr = get12HourTimeString(endTime);
              const booking = findBooking(
                expectedBookings,
                bookingInfo,
                currentDate
              );

              const oldStartTimeStr = get12HourTimeString(
                new Date(booking.start_utc)
              );
              const oldEndTimeStr = get12HourTimeString(
                new Date(booking.end_utc)
              );

              const newTimeRangeStr = `${startTimeStr} - ${endTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;

              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;

              cy.get(eventElemSelector).as("eventElem");
              cy.contains("#calendar-view .flex", "Bookings data").realClick();

              cy.get("@eventElem").scrollIntoView();
              cy.get("@eventElem")
                .contains(".fc-event-main-frame", username)
                .click();

              cy.contains("[data-cy-event-details] button", /edit/i)
                .click()
                .then(() => {
                  cy.contains(".fc-event-main-frame", newTimeRangeStr).should(
                    "not.exist"
                  );

                  cy.contains("#booking-form-dialog button", /cancel/i)
                    .click()
                    .then(() => {
                      cy.contains(
                        ".fc-event-main-frame",
                        newTimeRangeStr
                      ).should("not.exist");

                      cy.contains(eventElemSelector, oldTimeRangeStr).should(
                        "be.visible"
                      );
                    });
                });
            });

            it(`dragging and dropping the booking that starts in ${bookingInfo.starts_in} seconds, edits it`, () => {
              // Note: The length is very long so that the drop zone is visible on the view port
              cy.viewport(1440, 2080);
              const booking = findBooking(
                expectedBookings,
                bookingInfo,
                currentDate
              );

              const oldStartTimestamp = new Date(booking.start_utc);
              const oldStartTimeStr = get12HourTimeString(oldStartTimestamp);
              const oldEndTimeStr = get12HourTimeString(
                new Date(booking.end_utc)
              );

              // when we drag to the testTimeout band, any extra minutes less than 30 appear
              // since the slot lanes are of length 30 minutes
              const extraMinutes = oldStartTimestamp.getMinutes() % 30;
              const newTimestamp = new Date(
                testTimestamp.getTime() + extraMinutes * 60_000
              );
              const newStartTimeStr = get12HourTimeString(newTimestamp);
              const newEndTime = addSeconds(
                newTimestamp,
                booking.total_duration
              );
              const newEndTimeStr = get12HourTimeString(newEndTime);

              const newTimeRangeStr = `${newStartTimeStr} - ${newEndTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const newRowSelector = `.fc-timegrid-slot-lane[data-time="${testISOTimeStr}"]`;
              const newColSelector = `.fc-timegrid-col[data-date="${testISODateStr}"]`;

              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;

              cy.get(eventElemSelector).as("eventElem");

              cy.get("@eventElem").scrollIntoView();
              cy.contains(eventElemSelector, oldTimeRangeStr).should(
                "be.visible"
              );
              cy.contains(".fc-event-main-frame", newTimeRangeStr).should(
                "not.exist"
              );

              cy.get("@eventElem")
                .dragToGridCell(newRowSelector, newColSelector)
                .then(() => {
                  cy.wait("@bookings-list");
                  cy.contains(eventElemSelector, oldTimeRangeStr).should(
                    "not.exist"
                  );
                  cy.contains(".fc-event-main-frame", newTimeRangeStr)
                    .scrollIntoView()
                    .should("be.visible");
                });
            });

            it(`tapping the discard button on the booking starting in ${bookingInfo.starts_in} seconds, cancels it`, () => {
              cy.viewport(1440, 1080);
              const booking = findBooking(
                expectedBookings,
                bookingInfo,
                currentDate
              );

              const oldStartTimeStr = get12HourTimeString(
                new Date(booking.start_utc)
              );
              const oldEndTimeStr = get12HourTimeString(
                new Date(booking.end_utc)
              );

              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;

              cy.get(eventElemSelector).as("eventElem");
              cy.contains("#calendar-view .flex", "Bookings data").realClick();
              cy.get("[data-cy-event-details]").should("not.exist");

              cy.get("@eventElem").scrollIntoView();
              cy.contains(eventElemSelector, oldTimeRangeStr).should(
                "be.visible"
              );
              cy.get("@eventElem")
                .contains(".fc-event-main-frame", username)
                .click();

              cy.contains("[data-cy-event-details] button", /discard/i)
                .click()
                .then(() => {
                  cy.get("[data-cy-event-details]").should("not.exist");
                  cy.wait("@bookings-list");
                  cy.contains(eventElemSelector, oldTimeRangeStr).should(
                    "not.exist"
                  );
                });
            });
          } else {
            // when the booking does not belong to current user
            it(`dragging and dropping the another person's booking that starts in ${bookingInfo.starts_in} seconds, does nothing`, () => {
              cy.viewport(1440, 2080);
              const booking = findBooking(
                expectedBookings,
                bookingInfo,
                currentDate
              );
              const oldStartTimestamp = new Date(booking.start_utc);
              const oldStartTimeStr = get12HourTimeString(oldStartTimestamp);
              const oldEndTimeStr = get12HourTimeString(
                new Date(booking.end_utc)
              );
              // when we drag to the testTimeout band, any extra minutes less than 30 appear
              // since the slot lanes are of length 30 minutes
              const extraMinutes = oldStartTimestamp.getMinutes() % 30;
              const newTimestamp = new Date(
                testTimestamp.getTime() + extraMinutes * 60_000
              );
              const newStartTimeStr = get12HourTimeString(newTimestamp);
              const newEndTime = addSeconds(
                newTimestamp,
                booking.total_duration
              );
              const newEndTimeStr = get12HourTimeString(newEndTime);
              const newTimeRangeStr = `${newStartTimeStr} - ${newEndTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const newRowSelector = `.fc-timegrid-slot-lane[data-time="${testISOTimeStr}"]`;
              const newColSelector = `.fc-timegrid-col[data-date="${testISODateStr}"]`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              cy.get(eventElemSelector).as("eventElem");
              cy.get("@eventElem").scrollIntoView();
              cy.contains(eventElemSelector, oldTimeRangeStr).should(
                "be.visible"
              );
              cy.contains(".fc-event-main-frame", newTimeRangeStr).should(
                "not.exist"
              );
              cy.get("@eventElem")
                .dragToGridCell(newRowSelector, newColSelector)
                .then(() => {
                  cy.wait(100);
                  cy.contains(eventElemSelector, oldTimeRangeStr)
                    .scrollIntoView()
                    .should("be.visible");
                  cy.contains(".fc-event-main-frame", newTimeRangeStr).should(
                    "not.exist"
                  );
                });
            });
          }
        });
      });
    });
  });
});

/**
 * Converts seconds to a duration object
 *
 * @param totalSeconds - the total number of seconds to convert to duration
 * @returns - the duraiton string of format HH:mm:ss
 */
function convertSecToDuration(totalSeconds: number): {
  hours: number;
  minutes: number;
  seconds: number;
} {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return { hours, minutes, seconds };
}

/**
 * Converts seconds to a duration of format HH:mm:ss
 *
 * @param totalSeconds - the total number of seconds to convert to duration
 * @returns - the duraiton string of format HH:mm:ss
 */
function convertSecToDurationStr(totalSeconds: number): string {
  const { hours, minutes, seconds } = convertSecToDuration(totalSeconds);
  const hoursStr = hours.toString().padStart(2, "0");
  const minutesStr = minutes.toString().padStart(2, "0");
  const secondsStr = seconds.toString().padStart(2, "0");

  return `${hoursStr}:${minutesStr}:${secondsStr}.000`;
}

/**
 * Gets the time string as a 12 hour value without the PM/AM part e.g. 2:54
 *
 * @param value - the date valiue
 */
function get12HourTimeString(value: Date): string {
  return value
    .toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    })
    .split(" ")[0];
}

/**
 * Returns a new Date with the given extra number of seconds
 * @param value - the original Date value
 * @param seconds - the seconds to add
 */
function addSeconds(value: Date, seconds: number): Date {
  return new Date(value.getTime() + seconds * 1000);
}

/**
 * Extracts the locale date format of the date
 *
 * @param value - the date value
 */
function toLocaleDateStr(value: Date): string {
  return value.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/**
 * Extracts the ISO time format of the date
 *
 * @param value - the date value
 */
function toISOTimeStr(value: Date): string {
  return value.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/**
 * Extracts the ISO date of the date
 *
 * @param value - the date value
 */
function toISODateStr(value: Date): string {
  return value.toLocaleDateString("en-CA");
}

/**
 * Retrieves the booking that corresponds to the given booking info
 *
 * @param bookings - the list of available bookings
 * @param basicBookingInfo - the basic info of the booking to get
 * @param currentTimestamp - the timestamp now
 */
function findBooking(
  bookings: Booking[],
  { starts_in, duration }: { starts_in: number; duration: number },
  currentTimestamp: Date
): Booking {
  const now = currentTimestamp.getTime();
  const startTimestamp = new Date(now + starts_in * 1000);
  const endTimestamp = new Date(startTimestamp.getTime() + duration * 1000);
  const startTimestampStr = startTimestamp.toISOString();
  const endTimestampStr = endTimestamp.toISOString();

  const booking = bookings.find(
    (v) =>
      new Date(v.start_utc).toISOString() === startTimestampStr &&
      new Date(v.end_utc).toISOString() == endTimestampStr
  );
  if (!booking) {
    throw new Error(
      `booking starting in ${starts_in}s and of duration ${duration} not found`
    );
  }
  return booking;
}
