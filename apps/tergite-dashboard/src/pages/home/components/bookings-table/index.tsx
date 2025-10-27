import { Booking } from "../../../../../types";
import { bookingFilterFormProps } from "./filter-form";
import { bookingsTableColumns } from "./columns";
import { DataTable } from "@/components/ui/data-table";

export function BookingsTable({ data }: Props) {
  return (
    <DataTable
      columns={bookingsTableColumns}
      data={data}
      filterFormProps={bookingFilterFormProps}
    />
  );
}

interface Props {
  data: Booking[];
}
