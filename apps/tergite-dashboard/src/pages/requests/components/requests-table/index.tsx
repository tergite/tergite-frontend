import { DataTable } from "@/components/ui/data-table";
import { OnChangeFn, Row, RowSelectionState } from "@tanstack/react-table";
import type { UserRequest } from "@/lib/api/types";
import { columns } from "./columns";
import { filterFormProps } from "./filter-form";

export function MyRequestsTable({
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
  data: UserRequest[];
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  rowSelection?: RowSelectionState;
  onRowClick: (row: Row<UserRequest>) => void;
}
