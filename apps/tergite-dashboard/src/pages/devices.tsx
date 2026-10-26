import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import { DeviceStatusDiv } from "@/components/ui/device-status-div";
import { devicesQuery } from "@/lib/api/devices";
import type { Device } from "@/lib/api/types";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { Link, useLoaderData } from "react-router-dom";

export function Devices() {
  const { devices } = useLoaderData() as DeviceData;

  return (
    <main className="grid  auto-rows-fr gap-4 p-4 sm:px-6 sm:py-0 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {devices.length === 0 ? <div>No devices found.</div> : null}
      {devices.map((device) => (
        <Link key={device.name} to={`/devices/${device.name}`}>
          <Card className="text-sm flex flex-col justify-between h-full">
            <CardHeader className="pb-4">
              <div className="flex justify-between">
                <div className="font-semibold">{device.name}</div>{" "}
                <DeviceStatusDiv device={device} />
              </div>
            </CardHeader>
            <CardContent>
              <DetailItem label="Last seen">
                {device.last_online
                  ? DateTime.fromISO(device.last_online).toRelative()
                  : "N/A"}
              </DetailItem>
            </CardContent>
            <CardFooter className="flex">
              <div>
                <p className="text-muted-foreground">Qubits</p>
                <p className="text-4xl">{device.number_of_qubits}</p>
              </div>
            </CardFooter>
          </Card>
        </Link>
      ))}
    </main>
  );
}

interface DeviceData {
  devices: Device[];
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<DeviceData> => {
    const devices = await queryClient.ensureQueryData(devicesQuery);
    return { devices };
  });
}
