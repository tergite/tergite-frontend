import { DataTable } from "@/components/ui/data-table";

import { type ExtendedAppToken } from "@/lib/api/tokens";

import { columns } from "./columns";
import { filterFormProps } from "./filter-form";
import { OnChangeFn, Row, RowSelectionState } from "@tanstack/react-table";

export function TokensTable({
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
      //
      onRowClick={onRowClick}
    />
  );
}

interface Props {
  data: ExtendedAppToken[];
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  rowSelection?: RowSelectionState;
  onRowClick: (row: Row<ExtendedAppToken>) => void;
}
