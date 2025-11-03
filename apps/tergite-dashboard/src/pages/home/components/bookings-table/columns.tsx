import { SortHeader } from "@/components/ui/data-table";
import { Booking } from "../../../../../types";
import { ColumnDef } from "@tanstack/react-table";
import { DateTime, Duration } from "luxon";
import { toRelative } from "@/lib/utils";

export const bookingsTableColumns: ColumnDef<Booking>[] = [
  {
    accessorKey: "backend",
    header: () => <div className="hidden sm:table-cell">Device</div>,
    cell: ({ row }) => (
      <div data-booking-id={row.original.id} className="hidden sm:table-cell">
        {row.getValue("backend")}
      </div>
    ),
  },
  {
    accessorKey: "start_utc",
    header: ({ column }) => (
      <SortHeader
        column={column}
        label="Starts in"
        className="hidden md:table-cell "
      />
    ),
    cell: ({ row }) => {
      const startUtcString: string = row.getValue("start_utc");
      const startUtc = DateTime.fromISO(startUtcString);
      return (
        <div data-booking-id={row.original.id} className="hidden md:table-cell">
          {toRelative(startUtc)}
        </div>
      );
    },
  },
  {
    accessorKey: "total_duration",
    header: () => <div className="hidden sm:table-cell">Duration</div>,
    cell: ({ row }) => {
      const durationInSecs: number | null = row.getValue("total_duration");
      const duration = durationInSecs
        ? Duration.fromObject({
            seconds: durationInSecs,
          }).toHuman({ unitDisplay: "short" })
        : "N/A";
      return (
        <div data-booking-id={row.original.id} className="hidden sm:table-cell">
          {duration}
        </div>
      );
    },
  },
];
