import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { myProjectsQuery } from "@/lib/api/projects";
import { getMyRequestsQuery } from "@/lib/api/requests";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { useCallback, useState } from "react";
import { type AppState, type UserRequest } from "types";
import { MyRequestSidebar } from "./components/request-sidebar";
import { MyRequestsTable } from "./components/requests-table";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function MyRequests() {
  const { data: projects = [] } = useQuery(myProjectsQuery);
  const { data: requests = [] } = useQuery(
    getMyRequestsQuery({ role: "requester", projectList: projects })
  );

  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedRequest = findSelectedRow(requests ?? [], rowSelection);

  const handleRowClick = useCallback(
    (row: Row<UserRequest>) => {
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection]
  );

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card className="col-span-1 xl:col-span-3">
        <CardHeader>
          <CardDescription>Requests you have made</CardDescription>
        </CardHeader>
        <CardContent>
          <MyRequestsTable
            data={requests}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      <MyRequestSidebar
        request={selectedRequest}
        className="order-first xl:order-none col-span-1"
      />
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    const projects = await queryClient.ensureQueryData(myProjectsQuery);
    await queryClient.ensureQueryData(
      getMyRequestsQuery({ role: "requester", projectList: projects })
    );
    return {};
  });
}
