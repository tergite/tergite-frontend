import { type CalibrationValue, type DeviceCalibration } from "@/lib/api/types";

/** Each qubit's value of the property, by qubit index, for the charts */
export function getCalibrationPoints(
  calibration: DeviceCalibration,
  prop: QubitProp
): CalibrationDataPoint[] {
  return calibration.qubits.map((qubit, index) => {
    const point = qubit[prop];
    const value = typeof point?.value === "number" ? point.value : undefined;
    return { index, unit: point?.unit, value };
  });
}

export type QubitProp =
  | "t1_decoherence"
  | "t2_decoherence"
  | "frequency"
  | "anharmonicity"
  | "readout_assignment_error";

export type CalibrationDataPoint = {
  index: number;
  unit?: CalibrationValue["unit"];
  value?: number;
};
