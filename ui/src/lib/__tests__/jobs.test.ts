import { describe, expect, it } from "vitest";
import { getPollInterval } from "../api/jobs";

describe("getPollInterval", () => {
  const now = Date.parse("2026-11-06T12:00:00Z");

  it.each([
    ["2026-11-06T11:59:30Z", 2_000],
    ["2026-11-06T11:55:00Z", 10_000],
    ["2026-11-06T10:00:00Z", 30_000],
    [undefined, 2_000],
  ])("polls a job created at %s every %i ms", (createdAt, interval) => {
    expect(getPollInterval(createdAt, now)).toBe(interval);
  });
});
