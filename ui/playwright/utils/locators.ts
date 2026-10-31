import type { Locator } from "@playwright/test";

/** The first innermost selector match holding the text, like cy.contains(selector, text) */
export function innermost(scope: Locator, selector: string, text: string | RegExp): Locator {
  return scope
    .locator(selector, { hasText: text })
    .filter({ hasNot: scope.page().locator(selector, { hasText: text }) })
    .first();
}
