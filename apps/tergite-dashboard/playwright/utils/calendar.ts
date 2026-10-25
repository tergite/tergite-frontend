import { expect, type Locator, type Page } from "@playwright/test";

/** Resizes the viewport and waits for the calendar, which refits its tables after a delay */
export async function setCalendarViewportSize(page: Page, size: { width: number; height: number }) {
  await page.setViewportSize(size);
  await expect
    .poll(() =>
      page
        .locator("#calendar-view table.fc-col-header")
        .evaluate(
          (table: HTMLTableElement) => table.offsetWidth === table.parentElement!.clientWidth,
        ),
    )
    .toBe(true);
}

/** Clicks the calendar's slot at the given date (YYYY-MM-DD) and time (HH:mm:ss) */
export async function clickCalendarCell(calendar: Locator, dateStr: string, timeStr: string) {
  const column = calendar.locator(`.fc-timegrid-col[data-date="${dateStr}"]`);
  // the first slot with that time is the axis label
  const row = calendar.locator(`.fc-timegrid-slot[data-time="${timeStr}"]`).nth(1);
  await row.scrollIntoViewIfNeeded();
  const columnBox = (await column.boundingBox())!;
  const rowBox = (await row.boundingBox())!;
  const eventInit = {
    button: 0,
    clientX: columnBox.x + columnBox.width / 2,
    clientY: rowBox.y + rowBox.height / 2,
  };
  // sent to the slot itself, as Cypress's forced click does, since a booking may cover that point
  for (const type of ["pointerdown", "mousedown", "pointerup", "mouseup", "click"]) {
    await row.dispatchEvent(type, eventInit);
  }
}

/** Drags the element by its top left corner to the top left corner of where the row and column cross */
export async function dragToGridCell(page: Page, source: Locator, row: Locator, column: Locator) {
  await source.scrollIntoViewIfNeeded();
  const sourceBox = (await source.boundingBox())!;
  const rowBox = (await row.boundingBox())!;
  const columnBox = (await column.boundingBox())!;
  // a pixel inside, so that the points fall in the elements rather than on their edges
  await page.mouse.move(sourceBox.x + 1, sourceBox.y + 1);
  await page.mouse.down();
  await page.mouse.move(columnBox.x + 1, rowBox.y + 1, { steps: 10 });
  await page.mouse.up();
}
