// Tests that only read share the last reset of the database: a test that writes leaves it
// for the next one to reset. Each spec starts with a reset, as the flag starts set.
let hasWritten = true;

beforeEach(() => {
  // middleware, so it sees a write even when the spec stubs the response
  cy.intercept(
    { method: /^(POST|PUT|PATCH|DELETE)$/, middleware: true },
    () => {
      hasWritten = true;
    }
  );
});

Cypress.Commands.add("resetDatabase", () => {
  if (hasWritten) {
    hasWritten = false;
    cy.request(Cypress.env("DB_RESET_URL"));
  }
});

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      /**
       * Resets the database, unless no test has written to it since it was last reset
       */
      resetDatabase(): Chainable<void>;
    }
  }
}

export {};
