import { type Job } from "@/lib/api/types";
import { JobDetailDrawerContent } from "./detail-drawer";
import { jobFilterFormProps } from "./filter-form";
import { jobTableColumns } from "./columns";
import { DataTable } from "@/components/ui/data-table";

export function JobsTable({ data }: Props) {
  return (
    <DataTable
      columns={jobTableColumns}
      data={data}
      filterFormProps={jobFilterFormProps}
      getDrawerContent={(row) => <JobDetailDrawerContent job={row.original} />}
    />
  );
}

interface Props {
  data: Job[];
}
