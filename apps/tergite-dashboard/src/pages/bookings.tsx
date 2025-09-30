import EventCalendar from "@/components/ui/event-calendar";
import { bookingsOfBackendQuery } from "@/lib/api-client";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { LoaderFunctionArgs, useLoaderData } from "react-router-dom";
import { AppState } from "types";

export function Bookings() {
  // const queryClient = useQueryClient();
  const queryOptions = useLoaderData() as BookingsData;
  const { data: bookigs = [] } = useQuery(bookingsOfBackendQuery(queryOptions));
  const calendarEvents = useMemo(
    () =>
      bookigs.map((v) => ({
        title: v.user_fullname,
        start: v.start_utc,
        end: v.end_utc,
      })),
    [bookigs]
  );

  return (
    <main className="grid  auto-rows-fr gap-4 p-4 sm:px-6 sm:py-0 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      <EventCalendar events={calendarEvents} />
    </main>
  );
}

interface BookingsData {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: string;
  limit?: string;
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, _queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(
    async ({ params, request }: LoaderFunctionArgs) => {
      const { backend = "" } = params;
      const searchParams = new URL(request.url).searchParams;
      const skip = searchParams.get("skip");
      const limit = searchParams.get("limit");
      const user_id = searchParams.get("user_id");
      const min_start_utc = searchParams.get("min_start_utc");
      const max_start_utc = searchParams.get("max_start_utc");

      return {
        backend,
        skip,
        limit,
        user_id,
        min_start_utc,
        max_start_utc,
      } as BookingsData;
    }
  );
}
