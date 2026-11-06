import { Card, CardContent } from "@/components/ui/card";
import { getBookingsConfigQuery } from "@/lib/api/bookings";
import { currentUserQuery } from "@/lib/api/auth";
import { getDeviceCalibrationQuery, getDeviceQuery } from "@/lib/api/devices";
import type {
  BookingsConfig,
  Device,
  DeviceCalibration,
  User,
} from "@/lib/api/types";
import type { QubitProp } from "@/pages/device-detail/components/calibration-points";
import { LoaderFunctionArgs, useLoaderData } from "react-router-dom";

import { DeviceSummary } from "./components/device-summary";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalibrationDataTable } from "./components/calibration-data-table";
import { CalibrationBarChart } from "./components/calibration-bar-chart";
import { CalibrationHeader } from "./components/calibration-header";
import { CalibrationMapChart } from "./components/calibration-map-chart";
import { useState } from "react";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import type { ErrorInfo } from "@/lib/api/client";
import {
  BookingsCalendar,
  BookingsMetadata,
} from "./components/bookings-calendar";

const fieldLabels: { [k: string]: string } = {
  t1_decoherence: "T1 decoherence",
  t2_decoherence: "T2 decoherence",
  frequency: "Frequency",
  anharmonicity: "Anharmonicity",
  readout_assignment_error: "Readout error",
};

export function DeviceDetail() {
  const {
    device: defaultDevice,
    calibrationData: defaultCalibrationData,
    bookingsMetadata,
    bookingsConfig,
    bookingsError,
    currentUser,
    isAdmin,
  } = useLoaderData() as DeviceDetailData;
  const { data: device = defaultDevice } = useQuery(
    getDeviceQuery(defaultDevice.name),
  );
  // a device not calibrated yet has no calibration to poll for
  const { data: calibrationData = defaultCalibrationData } = useQuery({
    ...getDeviceCalibrationQuery(defaultDevice.name),
    enabled: !!defaultCalibrationData,
    // the loader's failed fetch stays in the cache, which a disabled query still throws
    throwOnError: false,
  });
  const notCalibrated = (
    <Card>
      <CardContent className="p-6 text-sm text-muted-foreground">
        {device.name} is not calibrated yet.
      </CardContent>
    </Card>
  );
  const [currentData, setCurrentData] = useState<QubitProp>("t1_decoherence");

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
          {!calibrationData ? (
            notCalibrated
          ) : (
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
          )}
        </TabsContent>
        <TabsContent id="graph-view" value="graph">
          {!calibrationData ? (
            notCalibrated
          ) : (
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
          )}
        </TabsContent>
        <TabsContent id="table-view" value="table">
          {!calibrationData ? (
            notCalibrated
          ) : (
            <Card>
              <CalibrationHeader device={device} currentData="Calibration" />
              <CardContent>
                <CalibrationDataTable data={calibrationData} />
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent id="calendar-view" value="calendar">
          <Card>
            <CalibrationHeader device={device} currentData="Bookings" />
            <CardContent>
              {bookingsConfig ? (
                <BookingsCalendar
                  bookingsMetadata={bookingsMetadata}
                  isAdmin={isAdmin}
                  currentUser={currentUser}
                  backend={device.name}
                  bookingsConfig={bookingsConfig}
                />
              ) : (
                <p
                  id="bookings-unavailable"
                  className="text-sm text-muted-foreground"
                >
                  Bookings are unavailable: {bookingsError}
                </p>
              )}
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

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(
    async ({
      params,
      request,
    }: LoaderFunctionArgs): Promise<DeviceDetailData> => {
      const { deviceName = "" } = params;
      // the calibration and the backend's bookings may be missing, and the rest still shows
      const [device, calibration, bookings, currentUser] = await Promise.all([
        queryClient.ensureQueryData(getDeviceQuery(deviceName)),
        fetchOrGetReason(
          queryClient.ensureQueryData(getDeviceCalibrationQuery(deviceName)),
        ),
        fetchOrGetReason(
          queryClient.ensureQueryData(getBookingsConfigQuery(deviceName)),
        ),
        queryClient.ensureQueryData(currentUserQuery),
      ]);
      const searchParams = new URL(request.url).searchParams;
      const bookingsMetadata: BookingsMetadata = {
        backend: deviceName,
        skip: searchParams.has("skip")
          ? Number(searchParams.get("skip"))
          : undefined,
        limit: searchParams.has("limit")
          ? Number(searchParams.get("limit"))
          : undefined,
        user_id: searchParams.get("user_id") ?? undefined,
        min_start_utc: searchParams.get("min_start_utc") ?? undefined,
        max_start_utc: searchParams.get("max_start_utc") ?? undefined,
      };
      const isAdmin = currentUser.roles.includes("admin");

      return {
        device,
        calibrationData: calibration.data,
        bookingsConfig: bookings.data,
        bookingsError: bookings.reason,
        bookingsMetadata,
        currentUser,
        isAdmin,
      };
    },
  );
}

interface DeviceDetailData {
  device: Device;
  // none for a device not calibrated yet
  calibrationData?: DeviceCalibration;
  bookingsMetadata: BookingsMetadata;
  // none when the device's backend cannot be reached, for the reason in bookingsError
  bookingsConfig?: BookingsConfig;
  bookingsError?: string;
  currentUser: User;
  isAdmin: boolean;
}

/** The fetch's data, or why it failed; a sign-in error is thrown on, to redirect */
async function fetchOrGetReason<T>(
  request: Promise<T>,
): Promise<{ data?: T; reason?: string }> {
  try {
    return { data: await request };
  } catch (error) {
    const { status, message } = error as ErrorInfo;
    if (status === 401 || status === 403) {
      throw error;
    }
    return { reason: message };
  }
}
