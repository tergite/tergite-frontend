import { Card, CardContent } from "@/components/ui/card";
import {
  bookingsOfBackendQuery,
  singleDeviceCalibrationQuery,
  singleDeviceQuery,
} from "@/lib/api-client";
import {
  AppState,
  Booking,
  Device,
  DeviceCalibration,
  QubitProp,
} from "../../../types";
import { LoaderFunctionArgs, useLoaderData } from "react-router-dom";

import { DeviceSummary } from "./components/device-summary";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalibrationDataTable } from "./components/calibration-data-table";
import { CalibrationBarChart } from "./components/calibration-bar-chart";
import { CalibrationHeader } from "./components/calibration-header";
import { CalibrationMapChart } from "./components/calibration-map-chart";
import { useMemo, useState } from "react";
import { QueryClient } from "@tanstack/react-query";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import EventCalendar from "@/components/ui/event-calendar";

const fieldLabels: { [k: string]: string } = {
  t1_decoherence: "T1 decoherence",
  t2_decoherence: "T2 decoherence",
  frequency: "Frequency",
  anharmonicity: "Anharmonicity",
  readout_assignment_error: "Readout error",
};

export function DeviceDetail() {
  const { device, calibrationData, bookings } =
    useLoaderData() as DeviceDetailData;
  const [currentData, setCurrentData] = useState<QubitProp>(
    QubitProp.T1_DECOHERENCE
  );
  const calendarEvents = useMemo(
    () =>
      bookings.map((v) => ({
        title: v.username,
        start: v.start_utc,
        end: v.end_utc,
      })),
    [bookings]
  );

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 md:gap-8 xl:grid-cols-4">
      <Tabs defaultValue="map" className="col-span-1 xl:pt-3 xl:col-span-3">
        <TabsList className="flex items-center justify-start flex-wrap h-auto space-y-1">
          <TabsTrigger value="map">Map view</TabsTrigger>
          <TabsTrigger value="graph">Graph view</TabsTrigger>
          <TabsTrigger value="table">Table view</TabsTrigger>
          <TabsTrigger value="calendar">Bookings</TabsTrigger>
        </TabsList>
        <TabsContent id="map-view" value="map">
          <Card>
            <CalibrationHeader
              device={device}
              currentData={currentData}
              fieldLabels={fieldLabels}
              onCurrentDataChange={setCurrentData}
            />
            <CardContent className="w-full min-w-[250px] h-[60vh] overflow-auto">
              <CalibrationMapChart
                data={calibrationData}
                minWidth={250}
                fieldLabels={fieldLabels}
                device={device}
                currentProp={currentData}
                currentLabel={fieldLabels[currentData]}
              />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent id="graph-view" value="graph">
          <Card className=" overflow-auto">
            <CalibrationHeader
              device={device}
              currentData={currentData}
              fieldLabels={fieldLabels}
              onCurrentDataChange={setCurrentData}
            />
            <CardContent className="w-full min-w-[250px] h-[60vh] overflow-auto">
              <CalibrationBarChart
                data={calibrationData}
                minWidth={250}
                fieldLabels={fieldLabels}
                currentProp={currentData}
              />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent id="table-view" value="table">
          <Card>
            <CalibrationHeader device={device} currentData="Calibration" />
            <CardContent>
              <CalibrationDataTable data={calibrationData} />
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent id="calendar-view" value="calendar">
          <Card>
            <CalibrationHeader device={device} currentData="Bookings" />
            <CardContent>
              <EventCalendar events={calendarEvents} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <DeviceSummary
        device={device}
        calibrationData={calibrationData}
        className="order-first xl:order-none mt-14 col-span-1"
      />
    </main>
  );
}

interface DeviceDetailData {
  device: Device;
  calibrationData: DeviceCalibration;
  bookings: Booking[];
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(
    async ({ params, request }: LoaderFunctionArgs) => {
      const { deviceName = "" } = params;

      // device
      const deviceQuery = singleDeviceQuery(deviceName);
      const cachedDevice = queryClient.getQueryData(deviceQuery.queryKey);
      const device =
        cachedDevice ?? (await queryClient.fetchQuery(deviceQuery));

      // calibration
      const calibrationQuery = singleDeviceCalibrationQuery(deviceName);
      const cachedCalibrationData = queryClient.getQueryData(
        calibrationQuery.queryKey
      );
      const calibrationData =
        cachedCalibrationData ??
        (await queryClient.fetchQuery(calibrationQuery));

      // bookings
      const searchParams = new URL(request.url).searchParams;
      const skip = searchParams.get("skip");
      const limit = searchParams.get("limit");
      const user_id = searchParams.get("user_id");
      const min_start_utc = searchParams.get("min_start_utc");
      const max_start_utc = searchParams.get("max_start_utc");

      const bookingsMetadata = {
        backend: deviceName,
        skip,
        limit,
        user_id,
        min_start_utc,
        max_start_utc,
      } as BookingsMetadata;

      const bookingsQuery = bookingsOfBackendQuery(bookingsMetadata);
      const cachedBookings = queryClient.getQueryData(bookingsQuery.queryKey);
      const bookings =
        cachedBookings ?? (await queryClient.fetchQuery(bookingsQuery));

      return { device, calibrationData, bookings };
    }
  );
}

interface BookingsMetadata {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
}
