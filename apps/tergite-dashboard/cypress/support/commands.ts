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
  (subject: JQuery<HTMLElement>, dateStr: string, timeStr: string) => {
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

Cypress.Commands.add(
  "dragToGridCell",
  { prevSubject: "element" },
  (subject: JQuery<HTMLElement>, rowSelector: string, colSelector: string) => {
    cy.wrap(subject)
      .scrollIntoView()
      .then(($source) => {
        cy.get(rowSelector).then(($row) => {
          cy.get(colSelector).then(($col) => {
            const rowRect = $row[0].getBoundingClientRect();
            const colRect = $col[0].getBoundingClientRect();
            const sourceRect = $source[0].getBoundingClientRect();

            return cy
              .wrap($source)
              .trigger("mousedown", {
                which: 1,
                button: 0,
                pageX: sourceRect.x,
                pageY: sourceRect.y,
              })
              .trigger("mousemove", {
                which: 1,
                pageX: colRect.x,
                pageY: rowRect.y,
              })
              .trigger("mouseup", { force: true });
          });
        });
      });

    return cy.wrap(subject);
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

      /**
       * Drags the previous element to the position of intersection between the elements identified by the two CSS selectors
       *
       * It yields the element that has been dragged
       *
       * @param rowSelector - the CSS selector for the element that is expected to be the row
       * @param colSelector - the CSS selector for the element that is expected to be the column
       */
      dragToGridCell(
        rowSelector: string,
        colSelector: string
      ): Chainable<Element | null>;
    }
  }
}

export {};
