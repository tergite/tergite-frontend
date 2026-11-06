import type { Locator, Page } from "@playwright/test";
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
// the run's compile and simulation take seconds; the page then polls every 2 s
const RUN_TIMEOUT_MS = 60_000;

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

  test("marks a circuit the backend refuses at its line", async ({ page, loginAs }) => {
    await loginAs(jane, `./run?job=${bellRun.job_id}`);
    await page.locator("#run-device").click();
    await page.getByRole("option", { name: /^sim_1q/ }).click();
    await replaceCircuit(page, BROKEN_CIRCUIT);

    const [response] = await Promise.all([
      waitForApi(page, "POST", "/me/jobs/"),
      page.getByRole("button", { name: "Run" }).click(),
    ]);

    expect(response.status()).toBe(422);
    await expect(page.locator("#circuit [role=alert]")).toHaveText(
      "circuit bell is not valid OpenQASM 3: line 4, column 0: missing ';' at 'bit'",
    );
    await expect(page.locator(".cm-lintRange-error")).toBeVisible();
  });

  // sim_1q is the stack's one device with workers: a simulated transmon behind dummy clusters
  test("runs a circuit on sim_1q and counts its shots", async ({ page, loginAs }) => {
    test.setTimeout(RUN_TIMEOUT_MS + 30_000);
    await loginAs(jane, `./run?job=${bellRun.job_id}`);
    await page.locator("#run-device").click();
    await page.getByRole("option", { name: /^sim_1q/ }).click();
    await page.locator("#run-name").fill("flip");
    await page.locator("#run-shots").fill("100");
    await replaceCircuit(page, FLIP_CIRCUIT);

    const [response] = await Promise.all([
      waitForApi(page, "POST", "/me/jobs/"),
      page.getByRole("button", { name: "Run" }).click(),
    ]);

    expect(response.status()).toBe(201);
    const results = page.locator("#results");
    await expect(results).toContainText("successful", { timeout: RUN_TIMEOUT_MS });
    await expect(results).toContainText("flip · sim_1q · 100 shots");
    const counts = await readCounts(results.getByRole("img", { name: /^Counts of flip/ }));
    expect(Object.values(counts).reduce((total, count) => total + count, 0)).toBe(100);
    // the flipped qubit reads 1 but for the simulator's readout noise and decay
    expect(counts["1"]).toBeGreaterThan(80);
    const run = page.locator("#runs").getByRole("row", { name: /flip/ });
    await expect(run).toContainText("successful");
  });
});

/** The counts a histogram's label names, by outcome */
async function readCounts(histogram: Locator): Promise<Record<string, number>> {
  const label = (await histogram.getAttribute("aria-label"))!;
  const pairs = label.replace(/^Counts of \w+: /, "").split(", ");
  return Object.fromEntries(
    pairs.map((pair) => {
      const [outcome, count] = pair.split(": ");
      return [outcome, Number(count)];
    }),
  );
}

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
