import { queryOptions } from "@tanstack/react-query";
import type {
  CalibrationValue,
  Device,
  DeviceCalibration,
} from "./types";
import { client } from "./client";

export const devicesQuery = queryOptions({
  queryKey: ["devices"],
  queryFn: async () => {
    const { data } = await client.GET("/devices/");
    // openapi-fetch's response type loses the schema's coordinate pairs to number[][]
    return data!.data as Device[];
  },
  throwOnError: true,
});

export function getDeviceQuery(name: string) {
  return queryOptions({
    queryKey: ["devices", name],
    queryFn: async () => {
      const { data } = await client.GET("/devices/{name}", {
        params: { path: { name } },
      });
      return data! as Device;
    },
    throwOnError: true,
  });
}

export function getDeviceCalibrationQuery(name: string) {
  return queryOptions({
    queryKey: ["calibrations", name],
    queryFn: async () => {
      const { data } = await client.GET("/calibrations/{name}", {
        params: { path: { name } },
      });
      return normalizeCalibrationData(data!);
    },
    throwOnError: true,
  });
}

/** Puts frequencies in GHz and decoherence times in microseconds */
function normalizeCalibrationData(item: DeviceCalibration): DeviceCalibration {
  const qubits = item.qubits.map((v) => ({
    ...v,
    frequency: convertHzToGHz(v.frequency),
    t1_decoherence: convertSecToMicrosec(v.t1_decoherence),
    t2_decoherence: convertSecToMicrosec(v.t2_decoherence),
    anharmonicity: convertHzToGHz(v.anharmonicity),
  }));
  return { ...item, qubits };
}

function convertHzToGHz(
  value?: CalibrationValue | null,
): CalibrationValue | null | undefined {
  return value?.unit === "Hz" && typeof value.value === "number"
    ? { ...value, unit: "GHz", value: value.value / 1000_000_000 }
    : value;
}

function convertSecToMicrosec(
  value?: CalibrationValue | null,
): CalibrationValue | null | undefined {
  return value?.unit === "s" && typeof value.value === "number"
    ? { ...value, unit: "us", value: value.value * 1000_000 }
    : value;
}
