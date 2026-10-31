import { queryOptions } from "@tanstack/react-query";
import type { GeneralMessage } from "./types";
import { client } from "./client";

export function getRecalibrationInfoQuery(backend: string) {
  return queryOptions({
    queryKey: ["admin", "recalibration", backend, "info"],
    queryFn: async () => {
      const { data } = await client.GET(
        "/admin/bcc/recalibration/{backend}/info",
        { params: { path: { backend } } },
      );
      return data!;
    },
    throwOnError: true,
  });
}

export async function startRecalibration(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST(
    "/admin/bcc/recalibration/{backend}/init",
    { params: { path: { backend } } },
  );
  return data!;
}

export async function stopRecalibration(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST(
    "/admin/bcc/recalibration/{backend}/cancel",
    { params: { path: { backend } } },
  );
  return data!;
}

export async function switchBackendOn(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/admin/bcc/switch/{backend}/on", {
    params: { path: { backend } },
  });
  return data!;
}

export async function switchBackendOff(
  backend: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/admin/bcc/switch/{backend}/off", {
    params: { path: { backend } },
  });
  return data!;
}
