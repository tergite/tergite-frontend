import type { Locator, Page } from "@playwright/test";
import { expect } from "../fixtures";

export interface TableFilter {
  inputs: Record<string, string>;
  status?: RegExp;
  /** The texts in the first column of the rows the filter should leave */
  expected: string[];
}

/** Opens the table's filter form and applies each filter in turn, clearing it after each */
export async function checkFilters(page: Page, filters: TableFilter[], all: string[]) {
  const table = page.locator(".bg-card table");
  const form = page.locator("[data-cy-filter-form]");
  await page.locator(".bg-card [aria-label='Filter']").click();
  await expect(form).toBeVisible();
  // the form resets itself to the table's filters in an effect run after it is painted, wiping anything typed sooner
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));

  for (const { inputs, status, expected } of filters) {
    for (const [name, value] of Object.entries(inputs)) {
      await form.locator(`input[name='${name}']`).fill(value);
    }
    if (status) {
      await form.locator("button[role='combobox']").click();
      await page.getByRole("option", { name: status }).click();
    }
    await form.locator("button[type='submit']").click();
    await expectFirstColumn(table, expected);

    await form.locator("button[type='reset']").click();
    await expectFirstColumn(table, all);
  }
}

async function expectFirstColumn(table: Locator, texts: string[]) {
  await expect(table.locator("tbody tr")).toHaveCount(texts.length || 1);
  for (const text of texts) {
    await expect(table.locator("tr td:first-child", { hasText: text }).first()).toBeVisible();
  }
}
