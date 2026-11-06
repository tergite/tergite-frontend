import type { Page } from "@playwright/test";
import { expect, readFixture, test, waitForApi } from "./fixtures";
import type { Job, User } from "./types";

// one qubit, so that the run needs no coupler on the simulator
const FLIP_CIRCUIT = [
  "OPENQASM 3.0;",
  'include "stdgates.inc";',
  "qubit[1] q;",
  "bit[1] c;",
  "x q[0];",
  "c[0] = measure q[0];",
];
const BROKEN_CIRCUIT = ["OPENQASM 3.0;", "qubit[1] q;", "x q[0]", "bit[1] c;"];

const jane = readFixture<User[]>("users").find(
  (v) => v.email === "jane.doe@example.com",
)!;
const bellRun = readFixture<Job[]>("jobs").find(
  (v) => v.source?.circuits[0]?.name === "bell",
)!;

test.describe("run page for jane.doe", () => {
  test("asks for a project before anything can run", async ({ page, loginAs }) => {
    await loginAs(jane, "./run");

    await expect(page.locator("#run-no-project")).toContainText(/pick a project/i);
  });

  test("opens a run's circuit and counts from its link", async ({
    page,
    loginAs,
  }) => {
    await loginAs(jane, `./run?job=${bellRun.job_id}`);

    const results = page.locator("#results");
    await expect(results).toContainText("successful");
    await expect(results.getByRole("img", { name: /^Counts of/ })).toHaveAttribute(
      "aria-label",
      "Counts of bell: 00: 507, 01: 15, 10: 13, 11: 489",
    );
    await expect(page.locator("#run-name")).toHaveValue("bell");
    await expect(page.locator(".cm-content")).toContainText("cx q[0], q[1];");

    await results.getByRole("tab", { name: "Counts" }).click();
    await expect(results.getByRole("row")).toHaveText([
      /Outcome\s*Count\s*Share/,
      /00\s*507\s*49\.5%/,
      /01\s*15\s*1\.5%/,
      /10\s*13\s*1\.3%/,
      /11\s*489\s*47\.8%/,
    ]);
  });

  test("marks a circuit MSS refuses at its line", async ({ page, loginAs }) => {
    await loginAs(jane, `./run?job=${bellRun.job_id}`);
    await replaceCircuit(page, BROKEN_CIRCUIT);

    const [response] = await Promise.all([
      waitForApi(page, "POST", "/me/jobs/"),
      page.getByRole("button", { name: "Run" }).click(),
    ]);

    expect(response.status()).toBe(422);
    await expect(page.locator("#circuit [role=alert]")).toHaveText(
      "Line 4: missing ';' at 'bit'",
    );
    await expect(page.locator(".cm-lintRange-error")).toBeVisible();
  });

  // the stack serves the backends' API without workers, so a backend has no device to run
  // on and refuses the upload; that still carries the circuit through MSS to the backend
  test("sends a circuit to the backend and reports what it answers", async ({
    page,
    loginAs,
  }) => {
    await loginAs(jane, `./run?job=${bellRun.job_id}`);
    await page.locator("#run-device").click();
    await page.getByRole("option", { name: /^Thor/ }).click();
    await page.locator("#run-name").fill("flip");
    await page.locator("#run-shots").fill("100");
    await replaceCircuit(page, FLIP_CIRCUIT);

    const [response] = await Promise.all([
      waitForApi(page, "POST", "/me/jobs/"),
      page.getByRole("button", { name: "Run" }).click(),
    ]);

    expect(response.status()).toBe(404);
    await expect(page.locator("#circuit [role=alert]")).toHaveText("'Thor' not found");
    const run = page.locator("#runs").getByRole("row", { name: /flip/ });
    await expect(run).toContainText("Thor");
    await expect(run).toContainText("100");
    await expect(run).toContainText("failed");
  });
});

/** Types the circuit over the editor's, closing completion before each new line */
async function replaceCircuit(page: Page, lines: string[]) {
  await page.locator(".cm-content").click();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.press("Delete");
  for (const line of lines) {
    await page.keyboard.type(line);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Enter");
  }
}
