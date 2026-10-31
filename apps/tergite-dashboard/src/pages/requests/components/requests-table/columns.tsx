import { SortHeader } from "@/components/ui/data-table";
import { ProgressStatus } from "@/components/ui/progress-status";
import { getUserRequestTitle } from "@/lib/utils";
import { ColumnDef } from "@tanstack/table-core";
import { DateTime } from "luxon";
import type { UserRequest } from "types";

export const columns: ColumnDef<UserRequest>[] = [
  {
    id: "title",
    accessorFn: (req) => getUserRequestTitle(req),
    header: ({ column }) => <SortHeader label="Request" column={column} />,
  },
  {
    id: "created_at",
    accessorFn: (row) => DateTime.fromISO(row.created_at).toRelative(),
    header: ({ column }) => <SortHeader label="Created" column={column} />,
  },
  {
    id: "approver_name",
    accessorFn: (row) => row.approver_name ?? "",
    header: ({ column }) => <SortHeader label="Decided by" column={column} />,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <ProgressStatus
        status={row.original.status}
        pendingValue="pending"
        successValue="approved"
        failureValue="rejected"
      />
    ),
  },
];
