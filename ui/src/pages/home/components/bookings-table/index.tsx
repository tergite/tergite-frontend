import type { Booking } from "@/lib/api/types";
import { bookingFilterFormProps } from "./filter-form";
import { bookingsTableColumns } from "./columns";
import { DataTable } from "@/components/ui/data-table";

export function BookingsTable({ data }: Props) {
  return (
    <DataTable
      columns={bookingsTableColumns}
      data={data}
      filterFormProps={bookingFilterFormProps}
      // a booking's id is unique only within its backend
      options={{ getRowId: (booking) => `${booking.backend}/${booking.id}` }}
    />
  );
}

interface Props {
  data: Booking[];
}
