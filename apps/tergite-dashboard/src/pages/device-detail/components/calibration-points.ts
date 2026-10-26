import type {
  CalibrationDataPoint,
  DeviceCalibration,
  QubitProp,
} from "../../../../types";

/** Each qubit's value of the property, by qubit index, for the charts */
export function getCalibrationPoints(
  calibration: DeviceCalibration,
  prop: QubitProp
): CalibrationDataPoint[] {
  return calibration.qubits.map((qubit, index) => ({
    ...(qubit[prop] ?? {}),
    index,
  }));
}
