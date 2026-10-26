import { SortHeader } from "@/components/ui/data-table";
import { ProgressStatus } from "@/components/ui/progress-status";
import { type Job, type JobStatus } from "@/lib/api/types";
import { ColumnDef } from "@tanstack/react-table";
import { DateTime, Duration } from "luxon";

export const jobTableColumns: ColumnDef<Job>[] = [
  {
    accessorKey: "job_id",
    header: "Job ID",
    cell: ({ row }) => (
      <div className="font-medium">{row.getValue("job_id")}</div>
    ),
  },
  {
    accessorKey: "device",
    header: () => <div className="hidden sm:table-cell">Device</div>,
    cell: ({ row }) => (
      <div className="hidden sm:table-cell">{row.getValue("device")}</div>
    ),
  },
  {
    accessorKey: "duration_in_secs",
    header: () => <div className="hidden sm:table-cell">Duration</div>,
    cell: ({ row }) => {
      const durationInSecs: number | null = row.getValue("duration_in_secs");
      const duration = durationInSecs
        ? Duration.fromObject({
            seconds: durationInSecs,
          }).toHuman()
        : "N/A";
      return <div className="hidden sm:table-cell">{duration}</div>;
    },
  },
  {
    accessorKey: "created_at",
    header: ({ column }) => (
      <SortHeader
        column={column}
        label="Created at"
        className="hidden md:table-cell "
      />
    ),
    cell: ({ row }) => {
      const createdAtString: string = row.getValue("created_at");
      const createdAt = DateTime.fromISO(createdAtString).toLocaleString(
        DateTime.DATETIME_MED
      );
      return <div className="hidden md:table-cell">{createdAt}</div>;
    },
  },
  {
    accessorKey: "status",
    header: () => <div className="text-right">Status</div>,
    cell: ({ row }) => {
      const status: JobStatus = row.getValue("status") || "pending";
      return (
        <ProgressStatus
          className="ml-auto"
          status={status}
          pendingValue={"pending"}
          successValue={"successful"}
          failureValue={"failed"}
        />
      );
    },
  },
];
