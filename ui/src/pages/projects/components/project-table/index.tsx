import { DataTable } from "@/components/ui/data-table";

import type { UserRequest, User, Project } from "@/lib/api/types";

import { getColumns } from "./columns";
import { filterFormProps } from "./filter-form";
import { OnChangeFn, Row, RowSelectionState } from "@tanstack/react-table";
import { useMemo } from "react";

export function ProjectsTable({
  data,
  onRowSelectionChange,
  rowSelection,
  onRowClick,
  currentUser,
  requests = [],
}: Props) {
  const columns = useMemo(
    () => getColumns({ currentUser, requests }),
    [currentUser, requests]
  );
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
  data: Project[];
  currentUser: User;
  requests: UserRequest[];
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  rowSelection?: RowSelectionState;
  onRowClick: (row: Row<Project>) => void;
}
