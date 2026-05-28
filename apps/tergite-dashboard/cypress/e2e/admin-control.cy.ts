/// <reference types="cypress" />
/// <reference types="cypress-real-events" />

import userList from "../fixtures/users.json";
import deviceList from "../fixtures/device-list.json";
import rawNoticeList from "../fixtures/notices.json";
import { generateJwt, getUsername } from "../../api/utils";
import { type Device, type User, UserRole } from "../../types";

/**
 * Shape of a notice record in the fixture (uses relative-time offsets instead
 * of absolute ISO strings so the data stays valid on any run date).
 */
interface NoticeFixture {
  id: string;
  starts_at_offset_hours: number;
  expires_at_offset_hours: number;
  target_user_ids: string[] | null;
  dismissed_by: string[];
}

/**
 * Returns every notice that is temporally active at the supplied reference
 * time, mirroring the admin NoticesCard query which omits user_id and sets
 * include_dismissed: true.
 *
 * A notice is active when:
 *  - it has already started  (starts_at <= now)
 *  - it has not yet expired  (expires_at >= now)
 *
 * No target_user_ids or dismissed_by filtering is applied because the admin
 * panel shows all system notices regardless of audience.
 */
function getAllActiveNotices(
  notices: NoticeFixture[],
  currentDate: Date
): NoticeFixture[] {
  const now = currentDate.getTime();
  return notices.filter((n) => {
    const startsAt = now + n.starts_at_offset_hours * 3_600_000;
    const expiresAt = now + n.expires_at_offset_hours * 3_600_000;
    return startsAt <= now && expiresAt >= now;
  });
}

const users = [...userList] as User[];
const devices = [...deviceList] as Device[];
const rawNotices = [...rawNoticeList] as NoticeFixture[];

const totalDeviceCount = devices.length;
const onlineDeviceCount = devices.filter((d) => d.is_online).length;

// First device in the fixture — selected by default on page load
const defaultDevice = devices[0]; // Loke: offline, 8 qubits, v2024.04.1
// First online device — used for tests that need an already-online backend
const onlineDevice = devices.find((d) => d.is_online)!; // Thor

users.forEach((user) => {
  const isAdmin = user.roles.includes(UserRole.ADMIN);
  const username = getUsername(user);
  const currentDateStr = Cypress.env("CURRENT_DATE");
  const currentDate = currentDateStr ? new Date(currentDateStr) : new Date();
  // The admin NoticesCard fetches all notices with no user_id filter, so the
  // expected count is every notice that has started and not yet expired.
  const activeNotices = getAllActiveNotices(rawNotices, currentDate);
  const activeNoticeCount = activeNotices.length;

  describe(`admin control page for ${username}`, () => {
    beforeEach(() => {
      const apiBaseUrl = Cypress.env("VITE_API_BASE_URL");
      const dbResetUrl = Cypress.env("DB_RESET_URL");
      const domain = Cypress.env("VITE_COOKIE_DOMAIN");
      const cookieName = Cypress.env("VITE_COOKIE_NAME");
      const secret = Cypress.env("JWT_SECRET");
      const audience = Cypress.env("AUTH_AUDIENCE");
      const cookieExpiry = Math.round((new Date().getTime() + 800_000) / 1000);

      cy.intercept("GET", `${apiBaseUrl}/devices/*`).as("device-req");
      cy.intercept("GET", `${apiBaseUrl}/me/projects/?is_active=true`).as(
        "my-project-list"
      );
      cy.intercept("GET", `${apiBaseUrl}/calibrations/*`).as("calibration");
      cy.intercept("GET", `${apiBaseUrl}/admin/recalibration/*/info`).as(
        "recalib-info"
      );
      cy.intercept("POST", `${apiBaseUrl}/admin/recalibration/*/init`).as(
        "start-recalib"
      );
      cy.intercept("POST", `${apiBaseUrl}/admin/recalibration/*/cancel`).as(
        "stop-recalib"
      );
      cy.intercept("POST", `${apiBaseUrl}/admin/switch/*/on`).as("switch-on");
      cy.intercept("POST", `${apiBaseUrl}/admin/switch/*/off`).as("switch-off");
      cy.intercept("GET", `${apiBaseUrl}/admin/notices*`).as("notices");
      cy.intercept("POST", `${apiBaseUrl}/admin/notices/`).as("create-notice");
      cy.intercept("DELETE", `${apiBaseUrl}/admin/notices/*`).as(
        "delete-notice"
      );
      cy.intercept("GET", `${apiBaseUrl}/counts/notices*`).as("notice-count");

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

      cy.request(`${dbResetUrl}`);
      cy.wait(500);

      cy.visit("/admin-control");
    });

    if (!isAdmin) {
      it("redirects non-admin users away from the control panel", () => {
        cy.url().should("not.include", "/admin-control");
      });
    } else {
      // Wait for the page to be fully loaded before each admin test
      beforeEach(() => {
        cy.wait("@my-project-list");
        cy.wait("@device-req");
      });

      // ── Page header & status bar ──────────────────────────────────────────

      it("renders the control panel header with a live device count badge", () => {
        cy.contains("h1", /control panel/i).should("be.visible");
        cy.contains(`${onlineDeviceCount}/${totalDeviceCount} online`).should(
          "be.visible"
        );
      });

      it("renders the system status bar with total, online, and selected device tiles", () => {
        // Each StatusTile has an uppercase label paragraph and a value paragraph
        cy.contains(/^Devices$/).should("be.visible");
        cy.contains(/^Devices$/)
          .parent()
          .contains(`${totalDeviceCount}`)
          .should("be.visible");

        cy.contains(/^Online$/).should("be.visible");
        cy.contains(/^Online$/)
          .parent()
          .contains(`${onlineDeviceCount}`)
          .should("be.visible");

        cy.contains(/^Selected$/).should("be.visible");
        cy.contains(/^Selected$/)
          .parent()
          .contains(defaultDevice.name)
          .should("be.visible");
      });

      // ── Device selector ───────────────────────────────────────────────────

      it("shows a device selector when there are multiple devices", () => {
        // With 6 devices in the fixture the selector must be present
        cy.get("[role='combobox']").first().should("be.visible");
      });

      it("switches the focused device when a different device is chosen", () => {
        cy.get("[role='combobox']").first().click();
        cy.contains(onlineDevice.name).click();

        // Status bar and backend card both reflect the newly selected device
        cy.contains(/^Selected$/)
          .parent()
          .contains(onlineDevice.name)
          .should("be.visible");
        cy.contains(/backend control/i)
          .closest("div")
          .contains(onlineDevice.name)
          .should("be.visible");
      });

      // ── BackendControlCard ────────────────────────────────────────────────

      it("shows the device name, qubit count, version, and Online/Offline badge", () => {
        cy.contains(/backend control/i).should("be.visible");
        // Default device is Loke (offline)
        cy.contains(/offline/i).first().should("be.visible");
        cy.contains(defaultDevice.name).should("be.visible");
        cy.contains(String(defaultDevice.number_of_qubits)).should(
          "be.visible"
        );
        cy.contains(defaultDevice.version).should("be.visible");
      });

      it("displays the toggle in the OFF position and 'Backend disabled' label for an offline device", () => {
        cy.contains(/backend disabled/i).should("be.visible");
        cy.contains(/not accepting new jobs/i).should("be.visible");
        cy.get("button[role='switch']")
          .first()
          .should("have.attr", "aria-checked", "false");
      });

      it("brings an offline backend online immediately on toggle click (no confirmation)", () => {
        cy.get("button[role='switch']")
          .first()
          .should("have.attr", "aria-checked", "false");
        cy.get("button[role='switch']").first().click();
        cy.wait("@switch-on");
        // No confirmation dialog should have appeared
        cy.contains(/take backend offline\?/i).should("not.exist");
        cy.contains(/backend enabled/i).should("be.visible");
        cy.contains(/accepting jobs from all users/i).should("be.visible");
        cy.get("button[role='switch']")
          .first()
          .should("have.attr", "aria-checked", "true");
      });

      it("requires confirmation before taking an online backend offline", () => {
        // Switch to an already-online device so we can test the offline flow
        cy.get("[role='combobox']").first().click();
        cy.contains(onlineDevice.name).click();
        cy.contains(/backend enabled/i).should("be.visible");
        cy.get("button[role='switch']")
          .first()
          .should("have.attr", "aria-checked", "true");

        // Clicking the toggle should open a confirmation dialog
        cy.get("button[role='switch']").first().click();
        cy.contains(/take backend offline\?/i).should("be.visible");

        // Cancelling should leave the backend online and not call the API
        cy.contains("button", /^Cancel$/i).click();
        cy.get("@switch-off.all").should("have.length", 0);
        cy.contains(/backend enabled/i).should("be.visible");

        // Confirming should call the switch-off endpoint
        cy.get("button[role='switch']").first().click();
        cy.contains("button", /take offline/i).click();
        cy.wait("@switch-off");
        cy.contains(/backend disabled/i).should("be.visible");
        cy.get("button[role='switch']")
          .first()
          .should("have.attr", "aria-checked", "false");
      });

      // ── CalibrationCard ───────────────────────────────────────────────────

      it("shows calibration metrics (T1, T2, qubits) for the selected device", () => {
        cy.wait("@calibration");
        cy.wait("@recalib-info");

        cy.contains(/^Calibration$/i).should("be.visible");
        cy.contains(defaultDevice.name).should("be.visible");
        // The fixture provides T1/T2 data for Loke
        cy.contains(/median t1/i).should("be.visible");
        cy.contains(/median t2/i).should("be.visible");
        cy.contains(/qubits/i).should("be.visible");
      });

      it("triggers recalibration only after the confirmation dialog is accepted", () => {
        cy.wait("@calibration");
        cy.wait("@recalib-info");

        // Click Trigger button — dialog should appear
        cy.contains("button", /trigger recalibration/i).click();
        cy.contains(/trigger recalibration\?/i).should("be.visible");

        // Cancel — API must NOT be called
        cy.contains("button", /^Cancel$/i).click();
        cy.get("@start-recalib.all").should("have.length", 0);

        // Confirm — API must be called and toast appears
        cy.contains("button", /trigger recalibration/i).click();
        cy.contains("button", /start calibration/i).click();
        cy.wait("@start-recalib");
        cy.contains(/recalibration started/i).should("be.visible");
      });

      // ── NoticesCard ───────────────────────────────────────────────────────

      it("renders the notices card with a 'New notice' form", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        cy.contains(/^Notices$/i).should("be.visible");
        cy.contains(/new notice/i).should("be.visible");
        cy.get("textarea#notice-message").should("be.visible");
        // Severity select defaults to INFO
        cy.contains(/info/i).should("be.visible");
      });

      it(`shows the correct active notice count badge (expected: ${activeNoticeCount})`, () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        // The card header shows "<count> active" when count > 0
        cy.contains(`${activeNoticeCount} active`).should("be.visible");
      });

      it("keeps the Post button disabled until the message textarea has content", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        cy.contains("button", /^Post$/i).should("be.disabled");
        cy.get("textarea#notice-message").type("Planned downtime window.");
        cy.contains("button", /^Post$/i).should("not.be.disabled");
      });

      it("shows active notices with severity labels visible to the current user", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        // The fixture has multiple active notices targeting the admin user
        cy.get("[aria-label='Delete notice']").first().should("be.visible");
        // Each banner shows a severity label (info / warning / critical)
        cy.contains(/\b(info|warning|critical)\b/i).should("be.visible");
      });

      it("creates a new notice and increments the active count, showing a success toast", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        const message =
          "Scheduled QPU maintenance tonight 22:00–02:00 UTC. Queue paused.";
        cy.get("textarea#notice-message").type(message);
        cy.contains("button", /^Post$/i).click();
        cy.wait("@create-notice");
        cy.wait("@notices");
        cy.wait("@notice-count");
        cy.contains(/notice posted/i).should("be.visible");
        // Active count should now be one more than the fixture baseline
        cy.contains(`${activeNoticeCount + 1} active`).should("be.visible");
      });

      it("deletes an active notice and decrements the active count, showing a success toast", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        cy.get("[aria-label='Delete notice']").first().click();
        cy.wait("@delete-notice");
        cy.wait("@notices");
        cy.wait("@notice-count");
        cy.contains(/notice deleted/i).should("be.visible");
        // Active count should drop by exactly one
        cy.contains(`${activeNoticeCount - 1} active`).should("be.visible");
      });

      it("paginates through notices with Previous/Next controls", () => {
        cy.wait("@notices");
        cy.wait("@notice-count");

        // On page 1, Previous should be disabled and Next enabled (>1 notice)
        cy.get("[aria-label='Go to previous page']").should(
          "have.attr",
          "aria-disabled",
          "true"
        );
        cy.get("[aria-label='Go to next page']").should(
          "have.attr",
          "aria-disabled",
          "false"
        );

        // Advance to page 2
        cy.get("[aria-label='Go to next page']").click();
        cy.wait("@notices");
        // Current page indicator updates
        cy.get("[aria-current='page']").should("have.text", "2");
        // Previous should now be enabled
        cy.get("[aria-label='Go to previous page']").should(
          "have.attr",
          "aria-disabled",
          "false"
        );
      });
    }
  });
});
