import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { describe, expect, it } from "vitest";
import type { Device, DeviceCalibration, Qubit } from "../../../../../types";
import { DeviceSummary } from "../device-summary";

const device = {
  name: "loke",
  version: "1",
  basis_gates: [],
  is_online: true,
  is_simulator: false,
  number_of_qubits: 4,
} as unknown as Device;

describe("DeviceSummary", () => {
  it("shows the median of the T1s present, ordered by value", () => {
    renderWithT1s([10, 9, 100, null]);

    expect(screen.getByText("Median T1").parentElement).toHaveTextContent(
      "10.00 us",
    );
  });

  it("averages the two middle T1s of an even count", () => {
    renderWithT1s([4, 30, 2, 20]);

    expect(screen.getByText("Median T1").parentElement).toHaveTextContent(
      "12.00 us",
    );
  });
});

function renderWithT1s(values: (number | null)[]) {
  const qubits = values.map((value) => ({
    t1_decoherence: value === null ? null : { value, unit: "us" },
  })) as unknown as Qubit[];
  const calibrationData = {
    name: "loke",
    version: "1",
    qubits,
    last_calibrated: "2025-01-01T00:00:00Z",
  } as DeviceCalibration;
  render(<DeviceSummary device={device} calibrationData={calibrationData} />);
}
