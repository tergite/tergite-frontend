import { describe, expect, it } from "vitest";
import { countOutcomes, getCircuitCounts } from "../qasm/counts";

describe("countOutcomes", () => {
  it("reads hex shots as bitstrings with bit 0 rightmost, padded to the bits", () => {
    expect(countOutcomes(["0x0", "0x3", "0x3", "0x1"], 2)).toEqual([
      { outcome: "00", count: 1 },
      { outcome: "01", count: 1 },
      { outcome: "11", count: 2 },
    ]);
  });
});

describe("getCircuitCounts", () => {
  it("counts each circuit's shots under its name", () => {
    const counts = getCircuitCounts({
      memory: [["0x1", "0x1"], ["0x0"]],
      meas_level: 2,
      circuits: [
        { name: "bell", num_clbits: 2 },
        { name: "idle", num_clbits: 1 },
      ],
    });

    expect(counts).toEqual([
      { name: "bell", counts: [{ outcome: "01", count: 2 }], shots: 2 },
      { name: "idle", counts: [{ outcome: "0", count: 1 }], shots: 1 },
    ]);
  });

  it("counts nothing measured at level 1, whose shots are IQ points", () => {
    const counts = getCircuitCounts({
      memory: [[[[0.1, 0.2]]]],
      meas_level: 1,
      circuits: [{ name: "iq", num_clbits: 1 }],
    });

    expect(counts).toEqual([]);
  });
});
