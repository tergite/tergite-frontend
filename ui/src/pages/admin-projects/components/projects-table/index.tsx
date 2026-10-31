import { DataTable } from "@/components/ui/data-table";

import type { AdminProject } from "@/lib/api/types";

import { columns } from "./columns";
import { filterFormProps } from "./filter-form";
import { OnChangeFn, Row, RowSelectionState } from "@tanstack/react-table";

export function AdminProjectsTable({
  data,
  onRowSelectionChange,
  rowSelection,
  onRowClick,
}: Props) {
  return (
    <DataTable
      columns={columns}
      data={data}
      filterFormProps={filterFormProps}
      options={{
        enableMultiRowSelection: false,
        onRowSelectionChange,
        state: { rowSelection },
      }}
      onRowClick={onRowClick}
    />
  );
}

interface Props {
  data: AdminProject[];
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  rowSelection?: RowSelectionState;
  onRowClick: (row: Row<AdminProject>) => void;
}
