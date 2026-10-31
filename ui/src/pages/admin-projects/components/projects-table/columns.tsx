import { SortHeader } from "@/components/ui/data-table";
import { HealthStatus } from "@/components/ui/health-status";
import { ColumnDef } from "@tanstack/table-core";
import type { AdminProject } from "@/lib/api/types";

export const columns: ColumnDef<AdminProject>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => <SortHeader label="Name" column={column} />,
    cell: ({ row }) => (
      <div className="font-medium">{row.getValue("name")}</div>
    ),
  },
  {
    accessorKey: "admin_email",
    header: ({ column }) => <SortHeader label="Admin" column={column} />,
  },
  {
    accessorKey: "qpu_seconds",
    header: ({ column }) => <SortHeader label="QPU seconds" column={column} />,
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => (
      <HealthStatus
        className="ml-auto lg:ml-0"
        isHealthy={row.original.is_active}
      />
    ),
    meta: {
      headerClassName: "text-right lg:text-left",
      rowClassName: "",
    },
  },
];
