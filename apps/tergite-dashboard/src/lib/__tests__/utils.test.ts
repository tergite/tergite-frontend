import { describe, expect, it } from "vitest";
import { CalibrationValue } from "../../../types";
import { getCalibrationMedians } from "../utils";

describe("getCalibrationMedians", () => {
  it("takes the median of the numbers present, ordered by value", () => {
    const qubits: Record<string, CalibrationValue | null>[] = [
      { t1: { value: 10, unit: "us" } },
      { t1: { value: 9, unit: "us" } },
      { t1: { value: 100, unit: "us" } },
      { t1: null },
    ];

    const medians = getCalibrationMedians(qubits, ["t1"]);

    expect(medians).toEqual({ t1: { value: 10, unit: "us" } });
  });

  it("averages the two middle numbers of an even count", () => {
    const qubits: Record<string, CalibrationValue | null>[] = [
      { t1: { value: 4, unit: "us" } },
      { t1: { value: 30, unit: "us" } },
      { t1: { value: 2, unit: "us" } },
      { t1: { value: 20, unit: "us" } },
    ];

    const medians = getCalibrationMedians(qubits, ["t1"]);

    expect(medians).toEqual({ t1: { value: 12, unit: "us" } });
  });
});
