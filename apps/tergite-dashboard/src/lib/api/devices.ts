import { queryOptions } from "@tanstack/react-query";
import type { Device, DeviceCalibration } from "../../../types";
import { normalizeCalibrationData } from "../utils";
import { client } from "./client";

export const devicesQuery = queryOptions({
  queryKey: ["devices"],
  queryFn: async () => {
    const { data } = await client.GET("/devices/");
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
      return normalizeCalibrationData(data! as DeviceCalibration);
    },
    throwOnError: true,
  });
}
