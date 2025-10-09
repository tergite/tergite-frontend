/// <reference types="cypress" />
// ***********************************************
// This example commands.ts shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })
//

Cypress.Commands.add("clipboard", () => {
  return cy.window().then((win) => {
    return win.navigator.clipboard.readText();
  });
});

Cypress.Commands.add(
  "clickCalendarCell",
  { prevSubject: "element" },
  (subject, dateStr, timeStr) => {
    const calendarEl = subject[0];

    const col = calendarEl.querySelector(
      `.fc-timegrid-col[data-date="${dateStr}"]`
    );
    const rows = calendarEl.querySelectorAll(
      `.fc-timegrid-slot[data-time="${timeStr}"]`
    );
    const row = rows[1]; // skip first (axis label)

    if (!col) {
      throw new Error(`column ${dateStr} does not exist`);
    } else if (!row) {
      throw new Error(`Slot ${timeStr} does not exist`);
    } else {
      cy.wrap(row).scrollIntoView();
      const colRect = col.getBoundingClientRect();
      const rowRect = row.getBoundingClientRect();

      const clickXPosition = colRect.left + colRect.width / 2 - rowRect.left;
      const clickYPosition = rowRect.height / 2;

      return cy
        .wrap(row)
        .click(clickXPosition, clickYPosition, { force: true });
    }
  }
);

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      /**
       * Returns what is on the clipboard
       */
      clipboard(): Chainable<string>;

      /**
       * Clicks a given calendar cell
       *
       * @param dateStr - the date string for the cell in the format YYYY-MM-DD
       * @param timeStr - the time string for the cell in format HH:mm:ss
       */
      clickCalendarCell(
        dateStr: string,
        timeStr: string
      ): Chainable<Element | null>;
    }
  }
}

export {};
