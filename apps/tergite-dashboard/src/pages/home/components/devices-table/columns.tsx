import { DeviceStatusDiv } from "@/components/ui/device-status-div";
import { type Device } from "@/lib/api/types";
import { ColumnDef } from "@tanstack/react-table";
import { DateTime } from "luxon";

export const deviceTableColumns: ColumnDef<Device>[] = [
  {
    accessorKey: "name",
    header: "Device",
    meta: { headerClassName: "", rowClassName: "font-medium" },
  },
  {
    accessorKey: "number_of_qubits",
    header: "Qubits",
    meta: {
      headerClassName: "hidden lg:table-cell",
      rowClassName: "hidden lg:table-cell",
    },
  },
  {
    accessorKey: "is_online",
    header: "Status",
    cell: ({ row }) => (
      <DeviceStatusDiv className="ml-auto lg:ml-0" device={row.original} />
    ),
    meta: {
      headerClassName: "text-right lg:text-left",
      rowClassName: "",
    },
  },
  {
    accessorKey: "last_online",
    header: "Last Seen",

    cell: ({ row }) => (
      <>
        {row.original.last_online
          ? DateTime.fromISO(row.original.last_online).toRelative()
          : "N/A"}
      </>
    ),
    meta: {
      headerClassName: "hidden lg:table-cell lg:text-right",
      rowClassName: "hidden lg:table-cell lg:text-right",
    },
  },
];
