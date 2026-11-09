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

import { currentUserQuery } from "@/lib/api/auth";
import { devicesQuery } from "@/lib/api/devices";
import { getMyJobsQuery } from "@/lib/api/jobs";
import { myProjectsQuery } from "@/lib/api/projects";
import { getUpcomingBookingsQuery } from "@/lib/api/bookings";
import type {
  Job,
  Device,
  Project,
  Booking,
  User,
} from "@/lib/api/types";
import { JobsTable } from "./components/jobs-table";
import { DevicesTable } from "./components/devices-table";
import {
  QueryClient,
  useQueries,
  useQuery,
  UseQueryResult,
} from "@tanstack/react-query";
import { loadOrRedirectIfAuthErr, tryQueryFetchMany } from "@/lib/loaders";
import { useAppStore } from "@/lib/app-state";
import { DateTime } from "luxon";
import { BookingsTable } from "./components/bookings-table";
import { Activity, ArrowUpRight, CalendarClock, Cpu } from "lucide-react";
import { MetricCard } from "./components/metric-card";

export function Home() {
  const {
    currentProject,
    devices: defaultDevices,
    jobs: defaultJobs,
    bookings: defaultBookings,
    currentUser,
  } = useLoaderData() as HomeData;
  const { data: devices = defaultDevices } = useQuery(devicesQuery);
  const { data: jobs = defaultJobs } = useQuery(
    getMyJobsQuery({ project_id: currentProject?.id })
  );

  const { data: bookings = defaultBookings } = useQueries({
    queries: getBookingsQueries(devices, currentUser),
    combine: combineMyBookingsQueries,
  });
  const devicesOnlineRatio = React.useMemo(
    () => {
      if (!devices.length) return 0;
      return Math.round(
        (devices.filter((v) => v.is_online).length / devices.length) * 100,
      );
    },
    [devices]
  );
  const onlineDevices = devices.filter((device) => device.is_online).length;
  const pendingJobs = jobs.filter((job) => job.status === "pending").length;
  const firstName = currentUser.email.split("@")[0].split(".")[0];

  return (
    <main className="grid flex-1 items-start gap-6 px-4 pb-6 sm:px-7">
      <section className="flex flex-col justify-between gap-4 pt-2 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Quantum computer
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Welcome back, <span className="capitalize">{firstName}</span>
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Monitor your quantum systems, compute queue, and reserved access.
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Quantum systems"
          value={`${onlineDevices}/${devices.length}`}
          detail={`${devicesOnlineRatio}% available`}
          Icon={Cpu}
        />
        <MetricCard
          label="Compute queue"
          value={String(pendingJobs)}
          detail={`${jobs.length} recent jobs`}
          Icon={Activity}
        />
        <MetricCard
          label="Reserved sessions"
          value={String(bookings.length)}
          detail="Upcoming bookings"
          Icon={CalendarClock}
        />
      </section>

      <div className="grid auto-rows-max items-start gap-5">
        <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
          <Card
            id="devices-online-piechart"
            className="relative overflow-hidden"
          >
            <CardHeader className="pb-2">
              <CardDescription className="text-xs font-semibold uppercase tracking-[0.14em]">
                Fleet availability
              </CardDescription>
              <CardTitle className="text-lg">Devices online</CardTitle>
            </CardHeader>
            <CardContent className="pb-5">
              <DonutChart
                percentFill={devicesOnlineRatio}
                thickness="5%"
              ></DonutChart>
            </CardContent>
          </Card>
          <Card
            id="devices-table"
            className="min-w-0"
            x-chunk="dashboard-05-chunk-0"
          >
            <CardHeader className="pb-3">
              <div className="flex justify-between">
                <div className="space-y-1.5">
                  <CardTitle>Devices</CardTitle>
                  <CardDescription>
                    Live availability across connected quantum systems
                  </CardDescription>
                </div>
                <Link
                  to="/devices"
                  className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  View fleet <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <DevicesTable data={devices.slice(0, 3)} />
            </CardContent>
          </Card>
        </div>
        <div className="grid gap-5 xl:grid-cols-5">
          <Card id="jobs-table" className="min-w-0 xl:col-span-3">
            <CardHeader className="px-7">
              <div className="flex justify-between">
                <div className="space-y-1.5">
                  <CardTitle>Jobs</CardTitle>
                  <CardDescription>
                    The status of your jobs in{" "}
                    {currentProject?.name || "all projects"}
                  </CardDescription>
                </div>
                <Link
                  to="/run"
                  className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  Run <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              <JobsTable data={jobs} />
            </CardContent>
          </Card>

          <Card id="bookings-table" className="min-w-0 xl:col-span-2">
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
  currentUser: User;
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<HomeData> => {
    const { currentProjectId } = useAppStore.getState();
    const [devices, projects, currentUser] = await Promise.all([
      queryClient.ensureQueryData(devicesQuery),
      queryClient.ensureQueryData(myProjectsQuery),
      queryClient.ensureQueryData(currentUserQuery),
    ]);
    const currentProject = projects.find((v) => v.id === currentProjectId);
    const [jobs, bookingsPerBackend] = await Promise.all([
      queryClient.ensureQueryData(
        getMyJobsQuery({ project_id: currentProject?.id })
      ),
      Promise.all(
        getBookingsQueries(devices, currentUser).map((v) =>
          tryQueryFetchMany(queryClient, v)
        )
      ),
    ]);

    return {
      devices,
      jobs,
      currentProject,
      currentUser,
      bookings: pickEarliestBookings(bookingsPerBackend),
    };
  });
}

/** The current user's upcoming bookings on each device, where one offline device fails alone */
function getBookingsQueries(devices: Device[], currentUser: User) {
  return devices.map(({ name: backend }) =>
    getUpcomingBookingsQuery({
      backend,
      user_id: currentUser.id,
      shouldThrowOnError: false,
    })
  );
}

/**
 * Combines the results got from for current user's bookings in multiple devices
 * into a single list
 *
 * @param results - the results from the useQueries call
 */
function combineMyBookingsQueries(results: UseQueryResult<Booking[], Error>[]) {
  const bookingLists = results
    .map((result) => result.data)
    .filter((v) => !!v) as Booking[][];
  return {
    data: pickEarliestBookings(bookingLists),
    pending: results.some((result) => result.isPending),
    error: results.some((result) => result.error),
  };
}

/**
 * Sorts all bookings in the list of lists of bookings
 * @param bookingLists - the list of bookings lists
 * @param limit - the maximum number of records to return
 */
function pickEarliestBookings(bookingLists: Booking[][], limit: number = 5): Booking[] {
  return bookingLists
    .flat(1)
    .sort((a, b) =>
      DateTime.fromISO(a.start_utc)
        .diff(DateTime.fromISO(b.start_utc))
        .as("seconds")
    )
    .slice(0, limit);
}
