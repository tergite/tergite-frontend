import * as React from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { Link, useLoaderData } from "react-router-dom";
import DonutChart from "@/components/ui/donut-chart";

import {
  currentUserQuery,
  devicesQuery,
  myJobsQuery,
  myProjectsQuery,
  upcomingBookingsQuery,
} from "@/lib/api-client";
import { Job, Device, AppState, Project, Booking } from "types";
import { JobsTable } from "./components/jobs-table";
import { DevicesTable } from "./components/devices-table";
import {
  DataTag,
  InitialDataFunction,
  QueryClient,
  useQueries,
  useQuery,
  UseQueryOptions,
  UseQueryResult,
} from "@tanstack/react-query";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import { DateTime } from "luxon";
import { BookingsTable } from "./components/bookings-table";

export function Home() {
  const {
    currentProject,
    devices: defaultDevices,
    jobs: defaultJobs,
    bookings: defaultBookings,
    bookingsQueries,
  } = useLoaderData() as HomeData;
  const { data: devices = defaultDevices } = useQuery(devicesQuery);
  const { data: jobs = defaultJobs } = useQuery(
    myJobsQuery({ project_id: currentProject?.id })
  );

  const { data: bookings = defaultBookings } = useQueries({
    queries: bookingsQueries,
    combine: combineMyBookingsQueries,
  });
  const devicesOnlineRatio = React.useMemo(
    () =>
      Math.round(
        (devices.filter((v) => v.is_online).length / devices.length) * 100
      ),
    [devices]
  );

  return (
    <main className="grid flex-1 items-start gap-4 p-4 sm:px-6 sm:py-0 lg:grid-cols-3 xl:grid-cols-3">
      <div className="grid auto-rows-max items-start gap-4 lg:col-span-3">
        <div className="grid gap-4 sm:grid-cols-[250px_auto_auto]">
          <Card className="grid-fit-content">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg">Devices Online</CardTitle>
            </CardHeader>
            <CardContent>
              <DonutChart
                percentFill={devicesOnlineRatio}
                thickness="5%"
              ></DonutChart>
            </CardContent>
          </Card>
          <Card className="sm:col-span-2" x-chunk="dashboard-05-chunk-0">
            <CardHeader className="pb-3">
              <div className="flex justify-between">
                <div className="space-y-1.5">
                  <CardTitle>Devices</CardTitle>
                  <CardDescription>List of available devices</CardDescription>
                </div>
                <Link to="/devices" className="font-normal underline">
                  View all
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <DevicesTable data={devices.slice(0, 3)} />
            </CardContent>
          </Card>
        </div>
        <div className="grid gap-4 sm:grid-cols-6">
          <Card className="sm:col-span-4">
            <CardHeader className="px-7">
              <CardTitle>Jobs</CardTitle>
              <CardDescription>
                The status of your jobs in{" "}
                {currentProject?.name || "all projects"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <JobsTable data={jobs} />
            </CardContent>
          </Card>

          <Card className="sm:col-span-2">
            <CardHeader className="px-7">
              <CardTitle>Upcoming Bookings</CardTitle>
              <CardDescription>My upcoming bookings</CardDescription>
            </CardHeader>
            <CardContent>
              <BookingsTable data={bookings} />
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}

interface HomeData {
  devices: Device[];
  jobs: Job[];
  bookings: Booking[];
  currentProject?: Project;
  bookingsQueries: (UseQueryOptions<
    Booking[],
    Error,
    Booking[],
    (string | undefined)[]
  > & {
    initialData?: InitialDataFunction<Booking[]> | undefined;
  } & {
    queryKey: DataTag<(string | undefined)[], Booking[]>;
  })[];
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    // devices
    const devices = await queryClient.ensureQueryData(devicesQuery);

    // project object
    const projects = await queryClient.ensureQueryData(myProjectsQuery);

    const currentProject = projects.filter(
      (v) => v.ext_id === appState.currentProjectExtId
    )[0];

    // jobs
    const jobs = await queryClient.ensureQueryData(
      myJobsQuery({ project_id: currentProject?.id })
    );

    // current user
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);

    // Bookings
    const bookingsQueries = devices.map(({ name: backend }) =>
      upcomingBookingsQuery({
        backend,
        user_id: currentUser.id,
      })
    );
    const bookingsPerBackend = await Promise.all(
      bookingsQueries.map((v) => queryClient.ensureQueryData(v))
    );

    const bookings = sortBookings(bookingsPerBackend);

    return {
      devices,
      jobs,
      currentProject,
      bookings,
      bookingsQueries,
    } as HomeData;
  });
}

/**
 * Combines the results got from for current user's bookings in multiple devices
 * into a single list
 *
 * @param results - the results from the useQueries call
 */
function combineMyBookingsQueries(results: UseQueryResult<Booking[], Error>[]) {
  const bookingLists = results.map((result) => result.data).filter((v) => !!v);
  return {
    data: sortBookings(bookingLists),
    pending: results.some((result) => result.isPending),
    error: results.some((result) => result.error),
  };
}

/**
 * Sorts all bookings in the list of lists of bookings
 * @param bookingLists - the list of bookings lists
 * @param limit - the maximum number of records to return
 */
function sortBookings(bookingLists: Booking[][], limit: number = 5): Booking[] {
  return bookingLists
    .flat(1)
    .sort((a, b) =>
      DateTime.fromISO(a.start_utc)
        .diff(DateTime.fromISO(b.start_utc))
        .as("seconds")
    )
    .slice(0, limit);
}
