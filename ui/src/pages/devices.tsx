import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DetailItem } from "@/components/ui/detail-item";
import { DeviceStatusDiv } from "@/components/ui/device-status-div";
import { devicesQuery } from "@/lib/api/devices";
import type { Device } from "@/lib/api/types";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { Link, useLoaderData } from "react-router-dom";
import { ArrowUpRight, Cpu } from "lucide-react";

export function Devices() {
  const { devices } = useLoaderData() as DeviceData;

  return (
    <main className="grid flex-1 gap-6 px-4 pb-6 sm:px-7">
      <section className="pt-2">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
          System fleet
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Quantum devices
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Select a device to inspect calibration data, availability, and
          scheduled access.
        </p>
      </section>

      <section className="grid auto-rows-fr gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {devices.length === 0 ? <div>No devices found.</div> : null}
        {devices.map((device) => (
          <Link
            key={device.name}
            to={`/devices/${device.name}`}
            className="group"
          >
            <Card className="flex h-full flex-col justify-between overflow-hidden text-sm transition-all duration-300 group-hover:-translate-y-1 group-hover:border-primary/30 group-hover:shadow-device-hover">
              <CardHeader className="pb-5">
                <div className="flex items-start justify-between">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/[0.08] text-primary">
                    <Cpu className="h-5 w-5" />
                  </span>
                  <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary" />
                </div>
                <div className="flex items-center justify-between pt-4">
                  <CardTitle className="text-xl">{device.name}</CardTitle>
                  <DeviceStatusDiv device={device} />
                </div>
              </CardHeader>
              <CardContent className="pb-5">
                <DetailItem label="Last telemetry">
                  {device.last_online
                    ? DateTime.fromISO(device.last_online).toRelative()
                    : "N/A"}
                </DetailItem>
              </CardContent>
              <CardFooter className="justify-between border-t bg-muted/35 py-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    Qubits
                  </p>
                  <p className="mt-1 font-display text-3xl font-semibold">
                    {device.number_of_qubits}
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-1 opacity-70">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <span
                      key={index}
                      className="h-1.5 w-1.5 rounded-full bg-primary/50"
                    />
                  ))}
                </div>
              </CardFooter>
            </Card>
          </Link>
        ))}
      </section>
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
