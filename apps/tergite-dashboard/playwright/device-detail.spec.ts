import { type Page } from "@playwright/test";
import { DateTime } from "luxon";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import { clickCalendarCell, dragToGridCell, setCalendarViewportSize } from "./utils/calendar";
import { type Booking, type BookingsConfig, type Device, type User } from "../types";

// the browser's, from the config's timezoneId, so that these dates match the page's
const TIME_ZONE = "Europe/Stockholm";

const users = readFixture<User[]>("users");
const devices = readFixture<Device[]>("device-list").slice(0, 2);
const calibrationProperties: { [k: string]: RegExp } = {
  t1_decoherence: /t1 decoherence/i,
  t2_decoherence: /t2 decoherence/i,
  anharmonicity: /anharmonicity/i,
  frequency: /frequency/i,
  readout_assignment_error: /readout error/i,
};
const medianCalibrationsDataMap =
  readFixture<{ [k: string]: { t1: string; t2: string; readout_error: string } }>(
    "median-calibrations",
  );
const bookingsConfigsMap = Object.fromEntries(
  readFixture<(BookingsConfig & { id: string })[]>("bookings-configs").map((v) => [v.id, v]),
);
const futureBookingsFixture = readFixture<{ starts_in: number; duration: number }[]>(
  "bookings",
).filter((v) => v.starts_in > 1500);
const currentDate = new Date(process.env.CURRENT_DATE!);
// TEST_THRESHOLD, as CI sets it, is the square root of the share of pixels that may differ
const testThreshold = parseFloat(process.env.TEST_THRESHOLD || "0.3");

test.use({ viewport: { width: 1280, height: 750 } });

users.slice(0, 2).forEach((user) => {
  devices.forEach((device) => {
    const calibrationMedians = medianCalibrationsDataMap[device.id];
    const bookingConfigs = bookingsConfigsMap[device.name];
    const username = user.email.split("@")[0];
    // the fixture's bookings are users[0]'s, and what the other user sees differs only for
    // someone else's booking, so every other test runs for the owner alone
    const isBookingsOwner = user === users[0];

    test.describe(`${device.name} device detail  for ${username}`, () => {
      test.beforeEach(async ({ page, loginAs }) => {
        await Promise.all([
          waitForApi(page, "GET", `/devices/${device.name}`),
          waitForApi(page, "GET", `/calibrations/${device.name}`),
          loginAs(user, `/devices/${device.name}`),
        ]);
      });

      if (isBookingsOwner) {
        test("renders the summary of the device", async ({ page }) => {
          await page.setViewportSize({ width: 1080, height: 750 });
          const summary = page.locator("#device-summary");

          const header = summary.locator(".grid", { hasText: device.name }).last();
          await expect(header.getByText(device.name).first()).toBeVisible();
          await expect(
            header.getByText(new RegExp(`version ${device.version}`, "i")).first(),
          ).toBeVisible();

          const statusRegex = device.is_online ? /online/i : /offline/i;
          const deviceTypeRegex = device.is_simulator ? /simulator/i : /physical/i;
          const details = summary.locator(".grid", { hasText: /details/i }).last();
          const detailItem = (label: RegExp) => details.locator("li", { hasText: label });
          await expect(detailItem(/status/i).getByText(statusRegex).first()).toBeVisible();
          await expect(
            detailItem(/basis gates/i).getByText(device.basis_gates.join(", ")).first(),
          ).toBeVisible();
          await expect(detailItem(/type/i).getByText(deviceTypeRegex).first()).toBeVisible();
          await expect(
            detailItem(/qubits/i).getByText(`${device.number_of_qubits}`).first(),
          ).toBeVisible();

          const calibrations = summary
            .locator(".grid", { hasText: /calibration information/i })
            .last();
          const calibrationItem = (label: RegExp) =>
            calibrations.locator("li", { hasText: label });
          await expect(
            calibrationItem(/median readout error/i)
              .getByText(calibrationMedians.readout_error)
              .first(),
          ).toBeVisible();
          await expect(
            calibrationItem(/median t1/i).getByText(calibrationMedians.t1).first(),
          ).toBeVisible();
          await expect(
            calibrationItem(/median t2/i).getByText(calibrationMedians.t2).first(),
          ).toBeVisible();

          const footer = summary.locator("div", { hasText: /last calibrated/i }).last();
          await expect(
            footer
              .getByText(
                /last calibrated \d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?) ago/i,
              )
              .first(),
          ).toBeVisible();
        });

        test("renders the map view", async ({ page }) => {
          for (const [property, regex] of Object.entries(calibrationProperties)) {
            await page.locator("button", { hasText: /map view/i }).first().click();
            await page.locator("button", { hasText: /property:/i }).first().click();
            await page.locator("#prop-selector").getByText(regex).first().click();

            await expect(page.locator("#map-view")).toHaveScreenshot(
              `map-view-for-${property}-of-${device.id}.png`,
              { maxDiffPixelRatio: Math.max(testThreshold, 0.35) ** 2 },
            );
          }
        });

        test("renders the graph view", async ({ page }) => {
          for (const [property, regex] of Object.entries(calibrationProperties)) {
            await page.locator("button", { hasText: /graph view/i }).first().click();
            await page.locator("button", { hasText: /property:/i }).first().click();
            await page.locator("#prop-selector").getByText(regex).first().click();

            await expect(page.locator("#graph-view")).toHaveScreenshot(
              `graph-view-for-${property}-of-${device.id}.png`,
              { maxDiffPixelRatio: testThreshold ** 2 },
            );
          }
        });

        test("renders the table view", async ({ page }) => {
          await page.locator("button", { hasText: /table view/i }).first().click();

          await expect(page.locator("#table-view")).toHaveScreenshot(
            `table-view-for-${device.id}.png`,
            { maxDiffPixelRatio: testThreshold ** 2 },
          );
        });
      }

      test.describe(`bookings for the ${device.name}`, () => {
        const username = users[0].email.split("@")[0];
        const currentUsername = user.email.split("@")[0];
        const timezoneOffset = -DateTime.now().setZone(TIME_ZONE).offset * 60;
        const testTimestamp = addSeconds(currentDate, 4 * 3_600 - timezoneOffset);
        const testLocaleDateStr = toLocaleDateStr(testTimestamp);
        const currentLocaleDateStr = toLocaleDateStr(currentDate);
        const testISODateStr = toISODateStr(testTimestamp);
        const testISOTimeStr = toISOTimeStr(testTimestamp);
        const currentISODateStr = toISODateStr(currentDate);
        const currentISOTimeStr = toISOTimeStr(currentDate);
        const defaultDuration = convertSecToDuration(bookingConfigs.min_time_slot_length);
        const defaultDurationStr = convertSecToDurationStr(bookingConfigs.min_time_slot_length);
        const invalidDurations = [
          bookingConfigs.min_time_slot_length - 60,
          bookingConfigs.max_time_slot_length + 60,
        ];
        let expectedBookings: Booking[] = [];

        test.beforeEach(async ({ page, apiUrl }) => {
          await page.clock.setFixedTime(currentDate);
          const response = await page.request.get(`${apiUrl}/bookings/${device.name}`);
          expectedBookings = (await response.json()).data;

          await Promise.all([
            waitForBookingsList(page, device.name),
            page.locator("button", { hasText: /bookings/i }).first().click(),
          ]);
          await expect(page.locator("[data-cy-calendar-event]").first()).toBeVisible();
        });

        if (isBookingsOwner) {
          test("renders the calendar view", async ({ page }) => {
            await page.locator("[data-cy-calendar-event]").first().scrollIntoViewIfNeeded();

            await expect(page.locator("#calendar-view")).toHaveScreenshot(
              `calendar-view-of-${device.id}.png`,
              { maxDiffPixelRatio: Math.max(testThreshold, 0.35) ** 2 },
            );
          });

          test("renders the basic details of a booking", async ({ page }) => {
            const events = page.locator("[data-cy-calendar-event]");
            for (let idx = 0; idx < (await events.count()); idx++) {
              const event = events.nth(idx);
              await event.scrollIntoViewIfNeeded();
              await expect(event.getByText(username).first()).toBeAttached();
              // for short bookings, the text gets cut off
              await expect(
                event.locator(".fc-event-time", { hasText: /\d\d?:\d\d - \d\d?:\d\d/ }).first(),
              ).toBeVisible();
            }
          });
        }

        test("renders the details of a booking on tapping the booking in the calendar", async ({
          page,
        }) => {
          const events = page.locator("[data-cy-calendar-event]");
          const details = page.locator("[data-cy-event-details]");
          for (let idx = 0; idx < (await events.count()); idx++) {
            await closeEventDetails(page);
            await expect(details).toHaveCount(0);

            const event = events.nth(idx);
            await event.scrollIntoViewIfNeeded();
            await event.locator(".fc-event-main-frame", { hasText: username }).click();
            await expect(details.getByText(username).first()).toBeVisible();
            await expect(details.getByText(/\d?\d:\d\d - \d?\d:\d\d/).first()).toBeVisible();
            await expect(
              details.locator("div", { hasText: /device/i }).last().getByText(device.name),
            ).toBeVisible();
            await expect(
              details
                .locator("div", { hasText: /duration/i })
                .last()
                .getByText(
                  /(\+?\d+ (seconds?)|(minutes?)|(hours?)|(days?)|(weeks?)|(months?)|(years?),?)+/i,
                )
                .first(),
            ).toBeVisible();
            // The first two events are in the past.
            if (idx > 1 && username === currentUsername) {
              await expect(
                details.locator("button.border.border-input", { hasText: /edit/i }),
              ).toBeVisible();
              await expect(
                details.locator("button.bg-destructive", { hasText: /discard/i }),
              ).toBeVisible();
            } else {
              await expect(details.locator("button", { hasText: /edit/i })).toHaveCount(0);
              await expect(details.locator("button", { hasText: /discard/i })).toHaveCount(0);
            }
          }
        });

        if (isBookingsOwner) {
          test("tapping an empty cell in the calendar opens a form for creating a new booking with that cell's start date", async ({
            page,
          }) => {
            await setCalendarViewportSize(page, { width: 1440, height: 1080 });
            const startTimeStr = get12HourTimeString(testTimestamp);
            const endTime = addSeconds(testTimestamp, bookingConfigs.min_time_slot_length);
            const endTimeStr = get12HourTimeString(endTime);
            const dialog = page.locator("#booking-form-dialog");
            const newEventTime = page
              .locator(".fc-event-time", { hasText: `${startTimeStr} - ${endTimeStr}` })
              .first();

            await expect(dialog).toHaveCount(0);
            await expect(newEventTime).toHaveCount(0);

            await clickCalendarCell(page.locator("#calendar-view"), testISODateStr, testISOTimeStr);
            await expect(dialog).toHaveCount(1);
            await expect(
              dialog.locator("h2", { hasText: /create new booking/i }),
            ).toBeVisible();
            await expect(
              dialog.locator("button#datetime-input", {
                hasText: new RegExp(`${testLocaleDateStr}, ${testISOTimeStr}`, "i"),
              }),
            ).toBeVisible();
            await expect(dialog.locator("input#duration[type='hidden']")).toHaveValue(
              defaultDurationStr,
            );
            await expect(dialog.locator("input#duration-hours[type='number']")).toHaveValue(
              `${defaultDuration.hours}`,
            );
            await expect(dialog.locator("input#duration-minutes[type='number']")).toHaveValue(
              `${defaultDuration.minutes}`,
            );
            await expect(dialog.locator("input#duration-seconds[type='number']")).toHaveValue(
              `${defaultDuration.seconds}`,
            );

            await dialog.locator("button", { hasText: /save/i }).click();
            await expect(newEventTime).toBeVisible();
          });

          test("Clicking cancel in the booking creation form cancels the event creation", async ({
            page,
          }) => {
            const startTimeStr = get12HourTimeString(testTimestamp);
            const endTime = addSeconds(testTimestamp, bookingConfigs.min_time_slot_length);
            const endTimeStr = get12HourTimeString(endTime);
            const newEventTime = page.locator(".fc-event-time", {
              hasText: `${startTimeStr} - ${endTimeStr}`,
            });

            await expect(page.locator("#booking-form-dialog")).toHaveCount(0);
            await expect(newEventTime).toHaveCount(0);

            await clickCalendarCell(page.locator("#calendar-view"), testISODateStr, testISOTimeStr);
            await page.locator("#booking-form-dialog button", { hasText: /cancel/i }).click();
            await expect(newEventTime).toHaveCount(0);
          });

          test("editing the default values in the creation form allows creation of booking with those values", async ({
            page,
          }) => {
            await setCalendarViewportSize(page, { width: 1440, height: 1080 });
            const startTimeStr = get12HourTimeString(testTimestamp);
            const duration = Math.min(
              bookingConfigs.max_time_slot_length,
              bookingConfigs.min_time_slot_length + 900,
            );
            const endTime = addSeconds(testTimestamp, duration);
            const endTimeStr = get12HourTimeString(endTime);
            const dialog = page.locator("#booking-form-dialog");
            const newEventTime = page
              .locator(".fc-event-time", { hasText: `${startTimeStr} - ${endTimeStr}` })
              .first();

            await expect(dialog).toHaveCount(0);
            await expect(newEventTime).toHaveCount(0);

            await clickCalendarCell(
              page.locator("#calendar-view"),
              currentISODateStr,
              currentISOTimeStr,
            );
            await fillDuration(page, duration);
            await dialog
              .locator("button#datetime-input", {
                hasText: new RegExp(`${currentLocaleDateStr}, ${currentISOTimeStr}`, "i"),
              })
              .click();
            await dialog
              .locator("[data-radix-popper-content-wrapper] input[type='time']")
              .fill(testISOTimeStr);

            await dialog.locator("button", { hasText: /save/i }).click();
            await expect(newEventTime).toBeVisible();
          });

          invalidDurations.forEach((duration) => {
            const titlePatch =
              duration > bookingConfigs.max_time_slot_length ? "greater than max" : "less than min";

            test(`entering a duration ${titlePatch} duration raises errors in the creation form`, async ({
              page,
            }) => {
              await setCalendarViewportSize(page, { width: 1440, height: 1080 });
              const startTimeStr = get12HourTimeString(testTimestamp);
              const endTime = addSeconds(testTimestamp, duration);
              const endTimeStr = get12HourTimeString(endTime);
              const minDurationStr = convertSecToDurationStr(bookingConfigs.min_time_slot_length);
              const maxDurationStr = convertSecToDurationStr(bookingConfigs.max_time_slot_length);
              const errMsg = `duration must be between ${minDurationStr} and ${maxDurationStr}`;
              const dialog = page.locator("#booking-form-dialog");
              const newEventTime = page.locator(".fc-event-time", {
                hasText: `${startTimeStr} - ${endTimeStr}`,
              });
              const error = dialog
                .locator("div.space-y-2", { hasText: /duration/i })
                .last()
                .locator("p.text-destructive", { hasText: new RegExp(errMsg) });

              await expect(dialog).toHaveCount(0);
              await expect(newEventTime).toHaveCount(0);

              await clickCalendarCell(
                page.locator("#calendar-view"),
                currentISODateStr,
                currentISOTimeStr,
              );
              await fillDuration(page, duration);
              await dialog
                .locator("button#datetime-input", {
                  hasText: new RegExp(`${currentLocaleDateStr}, ${currentISOTimeStr}`, "i"),
                })
                .click();
              await dialog
                .locator("[data-radix-popper-content-wrapper] input[type='time']")
                .fill(testISOTimeStr);
              await expect(error).toHaveCount(0);

              await dialog.locator("button", { hasText: /save/i }).click();
              await expect(error).toBeVisible();
              await expect(newEventTime).toHaveCount(0);
            });
          });

          test(`entering a start date that is in the past raises errors in the creation form`, async ({
            page,
          }) => {
            await setCalendarViewportSize(page, { width: 1440, height: 1080 });
            const startTimestamp = addSeconds(currentDate, -900);
            const startISOTimeStr = toISOTimeStr(startTimestamp);
            const startTimeStr = get12HourTimeString(startTimestamp);
            const duration = Math.min(
              bookingConfigs.max_time_slot_length,
              bookingConfigs.min_time_slot_length + 900,
            );
            const endTime = addSeconds(testTimestamp, duration);
            const endTimeStr = get12HourTimeString(endTime);
            const errMsg = `date must be in future`;
            const dialog = page.locator("#booking-form-dialog");
            const newEventTime = page.locator(".fc-event-time", {
              hasText: `${startTimeStr} - ${endTimeStr}`,
            });
            const error = dialog
              .locator("div.space-y-2", { hasText: /start/i })
              .last()
              .locator("p.text-destructive", { hasText: new RegExp(errMsg) });

            await expect(dialog).toHaveCount(0);
            await expect(newEventTime).toHaveCount(0);

            await clickCalendarCell(
              page.locator("#calendar-view"),
              currentISODateStr,
              currentISOTimeStr,
            );
            await fillDuration(page, duration);
            await dialog
              .locator("button#datetime-input", {
                hasText: new RegExp(`${currentLocaleDateStr}, ${currentISOTimeStr}`, "i"),
              })
              .click();
            await dialog
              .locator("[data-radix-popper-content-wrapper] input[type='time']")
              .fill(startISOTimeStr);
            await expect(error).toHaveCount(0);

            await dialog.locator("button", { hasText: /save/i }).click();
            await expect(error).toBeVisible();
            await expect(newEventTime).toHaveCount(0);
          });
        }

        futureBookingsFixture.slice(0, 2).forEach((bookingInfo) => {
          if (username === currentUsername) {
            test(`tapping the edit button on the booking that starts in ${bookingInfo.starts_in} seconds, opens edit form`, async ({
              page,
            }) => {
              await setCalendarViewportSize(page, { width: 1440, height: 1080 });
              const startTimeStr = get12HourTimeString(testTimestamp);
              const duration = Math.min(
                bookingConfigs.max_time_slot_length,
                bookingConfigs.min_time_slot_length + 900,
              );
              const endTime = addSeconds(testTimestamp, duration);
              const endTimeStr = get12HourTimeString(endTime);
              const booking = findBooking(expectedBookings, bookingInfo, currentDate);
              const oldStartTimeStr = get12HourTimeString(new Date(booking.start_utc));
              const oldEndTimeStr = get12HourTimeString(new Date(booking.end_utc));
              const newTimeRangeStr = `${startTimeStr} - ${endTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              const eventElem = page.locator(eventElemSelector);
              const dialog = page.locator("#booking-form-dialog");
              const details = page.locator("[data-cy-event-details]");
              const newEvent = page
                .locator(".fc-event-main-frame", { hasText: newTimeRangeStr })
                .first();

              await closeEventDetails(page);
              await expect(details).toHaveCount(0);

              await eventElem.scrollIntoViewIfNeeded();
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toBeVisible();
              await expect(newEvent).toHaveCount(0);
              await eventElem.locator(".fc-event-main-frame", { hasText: username }).click();

              await expect(dialog).toHaveCount(0);

              await details.locator("button", { hasText: /edit/i }).click();
              await expect(dialog).toBeVisible();
              await expect(details).toHaveCount(0);

              await fillDuration(page, duration);
              await dialog.locator("button#datetime-input").click();
              await dialog
                .locator("[data-radix-popper-content-wrapper] input[type='time']")
                .fill(testISOTimeStr);
              await Promise.all([
                waitForBookingsList(page, device.name),
                dialog.locator("button", { hasText: /save/i }).click(),
              ]);

              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toHaveCount(0);
              await newEvent.scrollIntoViewIfNeeded();
              await expect(newEvent).toBeVisible();
            });

            test(`tapping the cancel button when editing the booking starting in ${bookingInfo.starts_in} seconds, cancels everything`, async ({
              page,
            }) => {
              await setCalendarViewportSize(page, { width: 1440, height: 1080 });
              const startTimeStr = get12HourTimeString(testTimestamp);
              const duration = Math.min(
                bookingConfigs.max_time_slot_length,
                bookingConfigs.min_time_slot_length + 900,
              );
              const endTime = addSeconds(testTimestamp, duration);
              const endTimeStr = get12HourTimeString(endTime);
              const booking = findBooking(expectedBookings, bookingInfo, currentDate);
              const oldStartTimeStr = get12HourTimeString(new Date(booking.start_utc));
              const oldEndTimeStr = get12HourTimeString(new Date(booking.end_utc));
              const newTimeRangeStr = `${startTimeStr} - ${endTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              const eventElem = page.locator(eventElemSelector);
              const newEvent = page.locator(".fc-event-main-frame", { hasText: newTimeRangeStr });

              await closeEventDetails(page);

              await eventElem.scrollIntoViewIfNeeded();
              await eventElem.locator(".fc-event-main-frame", { hasText: username }).click();

              await page.locator("[data-cy-event-details] button", { hasText: /edit/i }).click();
              await expect(newEvent).toHaveCount(0);

              await page.locator("#booking-form-dialog button", { hasText: /cancel/i }).click();
              await expect(newEvent).toHaveCount(0);
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toBeVisible();
            });

            test(`dragging and dropping the booking that starts in ${bookingInfo.starts_in} seconds, edits it`, async ({
              page,
            }) => {
              // Note: The length is very long so that the drop zone is visible on the view port
              await setCalendarViewportSize(page, { width: 1440, height: 2080 });
              const booking = findBooking(expectedBookings, bookingInfo, currentDate);
              const oldStartTimestamp = new Date(booking.start_utc);
              const oldStartTimeStr = get12HourTimeString(oldStartTimestamp);
              const oldEndTimeStr = get12HourTimeString(new Date(booking.end_utc));
              // when we drag to the testTimeout band, any extra minutes less than 30 appear
              // since the slot lanes are of length 30 minutes
              const extraMinutes = getMinutes(oldStartTimestamp) % 30;
              const newTimestamp = new Date(testTimestamp.getTime() + extraMinutes * 60_000);
              const newStartTimeStr = get12HourTimeString(newTimestamp);
              const newEndTime = addSeconds(newTimestamp, booking.total_duration);
              const newEndTimeStr = get12HourTimeString(newEndTime);
              const newTimeRangeStr = `${newStartTimeStr} - ${newEndTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              const eventElem = page.locator(eventElemSelector);
              const newEvent = page
                .locator(".fc-event-main-frame", { hasText: newTimeRangeStr })
                .first();

              await eventElem.scrollIntoViewIfNeeded();
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toBeVisible();
              await expect(newEvent).toHaveCount(0);

              await Promise.all([
                waitForBookingsList(page, device.name),
                dragToGridCell(
                  page,
                  eventElem,
                  page.locator(`.fc-timegrid-slot-lane[data-time="${testISOTimeStr}"]`).first(),
                  page.locator(`.fc-timegrid-col[data-date="${testISODateStr}"]`).first(),
                ),
              ]);
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toHaveCount(0);
              await newEvent.scrollIntoViewIfNeeded();
              await expect(newEvent).toBeVisible();
            });

            test(`tapping the discard button on the booking starting in ${bookingInfo.starts_in} seconds, cancels it`, async ({
              page,
            }) => {
              await setCalendarViewportSize(page, { width: 1440, height: 1080 });
              const booking = findBooking(expectedBookings, bookingInfo, currentDate);
              const oldStartTimeStr = get12HourTimeString(new Date(booking.start_utc));
              const oldEndTimeStr = get12HourTimeString(new Date(booking.end_utc));
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              const eventElem = page.locator(eventElemSelector);
              const details = page.locator("[data-cy-event-details]");

              await closeEventDetails(page);
              await expect(details).toHaveCount(0);

              await eventElem.scrollIntoViewIfNeeded();
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toBeVisible();
              await eventElem.locator(".fc-event-main-frame", { hasText: username }).click();

              await Promise.all([
                waitForBookingsList(page, device.name),
                details.locator("button", { hasText: /discard/i }).click(),
              ]);
              await expect(details).toHaveCount(0);
              await expect(
                page.locator(eventElemSelector, { hasText: oldTimeRangeStr }),
              ).toHaveCount(0);
            });
          } else {
            test(`dragging and dropping the another person's booking that starts in ${bookingInfo.starts_in} seconds, does nothing`, async ({
              page,
            }) => {
              await setCalendarViewportSize(page, { width: 1440, height: 2080 });
              const booking = findBooking(expectedBookings, bookingInfo, currentDate);
              const oldStartTimestamp = new Date(booking.start_utc);
              const oldStartTimeStr = get12HourTimeString(oldStartTimestamp);
              const oldEndTimeStr = get12HourTimeString(new Date(booking.end_utc));
              // when we drag to the testTimeout band, any extra minutes less than 30 appear
              // since the slot lanes are of length 30 minutes
              const extraMinutes = getMinutes(oldStartTimestamp) % 30;
              const newTimestamp = new Date(testTimestamp.getTime() + extraMinutes * 60_000);
              const newStartTimeStr = get12HourTimeString(newTimestamp);
              const newEndTime = addSeconds(newTimestamp, booking.total_duration);
              const newEndTimeStr = get12HourTimeString(newEndTime);
              const newTimeRangeStr = `${newStartTimeStr} - ${newEndTimeStr}`;
              const oldTimeRangeStr = `${oldStartTimeStr} - ${oldEndTimeStr}`;
              const eventElemSelector = `[data-cy-calendar-event][data-booking-id="${booking.id}"]`;
              const eventElem = page.locator(eventElemSelector);
              const oldEvent = page.locator(eventElemSelector, { hasText: oldTimeRangeStr });
              const newEvent = page.locator(".fc-event-main-frame", { hasText: newTimeRangeStr });

              await eventElem.scrollIntoViewIfNeeded();
              await expect(oldEvent).toBeVisible();
              await expect(newEvent).toHaveCount(0);

              await dragToGridCell(
                page,
                eventElem,
                page.locator(`.fc-timegrid-slot-lane[data-time="${testISOTimeStr}"]`).first(),
                page.locator(`.fc-timegrid-col[data-date="${testISODateStr}"]`).first(),
              );
              await oldEvent.scrollIntoViewIfNeeded();
              await expect(oldEvent).toBeVisible();
              await expect(newEvent).toHaveCount(0);
            });
          }
        });
      });
    });
  });
});

/** Waits for the response to the list of the device's bookings, rather than its config */
function waitForBookingsList(page: Page, deviceName: string) {
  return page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === `/bookings/${deviceName}`,
  );
}

/** Clicks the calendar's header, away from any open booking details */
async function closeEventDetails(page: Page) {
  await page.locator("#calendar-view .flex", { hasText: "Bookings data" }).first().click();
}

async function fillDuration(page: Page, totalSeconds: number) {
  const { hours, minutes, seconds } = convertSecToDuration(totalSeconds);
  const dialog = page.locator("#booking-form-dialog");
  await dialog.locator("input#duration-hours[type='number']").fill(`${hours}`);
  await dialog.locator("input#duration-minutes[type='number']").fill(`${minutes}`);
  await dialog.locator("input#duration-seconds[type='number']").fill(`${seconds}`);
}

function convertSecToDuration(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return { hours, minutes, seconds };
}

/** Formats the seconds as HH:mm:ss.SSS */
function convertSecToDurationStr(totalSeconds: number): string {
  const { hours, minutes, seconds } = convertSecToDuration(totalSeconds);
  const [hoursStr, minutesStr, secondsStr] = [hours, minutes, seconds].map((v) =>
    v.toString().padStart(2, "0"),
  );

  return `${hoursStr}:${minutesStr}:${secondsStr}.000`;
}

/** Formats the time in 12 hours without the AM/PM, e.g. 2:54 */
function get12HourTimeString(value: Date): string {
  return value
    .toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: TIME_ZONE,
    })
    .split(/\s/)[0];
}

function getMinutes(value: Date): number {
  return DateTime.fromJSDate(value).setZone(TIME_ZONE).minute;
}

function addSeconds(value: Date, seconds: number): Date {
  return new Date(value.getTime() + seconds * 1000);
}

function toLocaleDateStr(value: Date): string {
  return value.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: TIME_ZONE,
  });
}

function toISOTimeStr(value: Date): string {
  return value.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: TIME_ZONE,
  });
}

function toISODateStr(value: Date): string {
  return value.toLocaleDateString("en-CA", { timeZone: TIME_ZONE });
}

function findBooking(
  bookings: Booking[],
  { starts_in, duration }: { starts_in: number; duration: number },
  currentTimestamp: Date,
): Booking {
  const startTimestamp = new Date(currentTimestamp.getTime() + starts_in * 1000);
  const endTimestamp = new Date(startTimestamp.getTime() + duration * 1000);
  const booking = bookings.find(
    (v) =>
      new Date(v.start_utc).toISOString() === startTimestamp.toISOString() &&
      new Date(v.end_utc).toISOString() === endTimestamp.toISOString(),
  );
  if (!booking) {
    throw new Error(`booking starting in ${starts_in}s and of duration ${duration} not found`);
  }
  return booking;
}
