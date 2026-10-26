import { QueryClient, queryOptions } from "@tanstack/react-query";
import { DateTime } from "luxon";
import type {
  Booking,
  GeneralMessage,
  NewBookingInfo,
} from "./types";
import type { ErrorInfo } from "@/lib/api/client";
import { client } from "./client";

/** The backend's bookings from now on, by default the next five */
export function getUpcomingBookingsQuery(options: {
  backend: string;
  user_id?: string;
  max_start_utc?: string;
  skip?: number;
  limit?: number;
  shouldThrowOnError?: boolean;
}) {
  const {
    backend,
    user_id,
    max_start_utc,
    skip = 0,
    limit = 5,
    shouldThrowOnError = true,
  } = options;
  return queryOptions({
    // min_start_utc is left out as it moves on every refetch
    queryKey: ["bookings", backend, user_id, "upcoming", max_start_utc, limit, skip],
    queryFn: async () =>
      await getBookings(backend, {
        user_id,
        min_start_utc: DateTime.utc().toISO(),
        max_start_utc,
        skip,
        limit,
      }),
    throwOnError: shouldThrowOnError,
  });
}

/** @param options.sort - the fields to sort by, descending where prefixed with "-" */
export function getBookingsOfBackendQuery(options: {
  backend: string;
  user_id?: string;
  min_start_utc?: string;
  max_start_utc?: string;
  skip?: number;
  limit?: number;
  sort?: string[];
}) {
  const { backend, skip = 0, ...rest } = options;
  const { user_id, min_start_utc, max_start_utc, limit, sort } = rest;
  return queryOptions({
    queryKey: [
      "bookings",
      backend,
      user_id,
      min_start_utc,
      max_start_utc,
      limit,
      skip,
      sort,
    ],
    queryFn: async () => await getBookings(backend, { ...rest, skip }),
    throwOnError: true,
  });
}

export function getBookingsConfigQuery(backend: string) {
  return queryOptions({
    queryKey: ["bookings", backend, "config"],
    queryFn: async () => {
      const { data } = await client.GET("/bookings/{backend}/config", {
        params: { path: { backend } },
      });
      return data!;
    },
    throwOnError: true,
  });
}

export async function createNewBooking(
  backend: string,
  payload: NewBookingInfo,
): Promise<Booking> {
  const { data } = await client.POST("/bookings/{backend}", {
    params: { path: { backend } },
    body: payload,
  });
  return data!;
}

export async function updateBooking(
  backend: string,
  id: string,
  payload: NewBookingInfo,
): Promise<Booking> {
  await cancelBooking(backend, id);
  return await createNewBooking(backend, payload);
}

/** Throws when the backend reports anything but success */
export async function cancelBooking(
  backend: string,
  id: string,
): Promise<GeneralMessage> {
  const { data } = await client.POST("/bookings/{backend}/{booking_id}/cancel", {
    params: { path: { backend, booking_id: id } },
  });
  const response = data!;
  if (response.status !== "success") {
    const error = new Error(`${response.status}: ${response.detail}`) as ErrorInfo;
    error.statusText = response.status;
    throw error;
  }
  return response;
}

export function refreshBookingsQueries(queryClient: QueryClient, backend: string) {
  return queryClient.invalidateQueries({ queryKey: ["bookings", backend] });
}

async function getBookings(
  backend: string,
  query: {
    user_id?: string;
    min_start_utc?: string;
    max_start_utc?: string;
    skip?: number;
    limit?: number;
    sort?: string[];
  },
): Promise<Booking[]> {
  const { data } = await client.GET("/bookings/{backend}", {
    params: { path: { backend }, query },
  });
  return data!.data;
}
