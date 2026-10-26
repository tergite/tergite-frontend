import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { getAllAdminProjectsQuery } from "@/lib/api/projects";
import { getAllUserRequestsQuery } from "@/lib/api/requests";
import { currentUserQuery } from "@/lib/api/auth";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useLoaderData } from "react-router-dom";
import {
  ErrorInfo,
  User,
  UserRequestStatus,
  UserRole,
  type UserRequest,
} from "../../../types";
import { AdminRequestsTable } from "./components/requests-table";
import { RequestsSidebar } from "./components/requests-sidebar";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function AdminRequests() {
  const { currentUser } = useLoaderData() as AdminRequestsData;
  const { data: projects = [] } = useQuery(
    getAllAdminProjectsQuery({ currentUser })
  );
  const { data: requests = [] } = useQuery(
    getAllUserRequestsQuery({
      status: UserRequestStatus.PENDING,
      currentUser,
      projectList: projects,
    })
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

  const handleRequestReaction = useCallback(() => {
    setRowSelection({});
  }, [setRowSelection]);

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card className="col-span-1 xl:col-span-3">
        <CardHeader>
          <CardDescription>Pending User requests</CardDescription>
        </CardHeader>
        <CardContent>
          <AdminRequestsTable
            data={requests}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      <RequestsSidebar
        request={selectedRequest}
        className="order-first xl:order-none col-span-1"
        onApproval={handleRequestReaction}
        onRejection={handleRequestReaction}
      />
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<AdminRequestsData> => {
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);

    if (!currentUser.roles.includes(UserRole.ADMIN)) {
      const error = new Error("user should be an admin") as ErrorInfo;
      error.status = 403;
      throw error;
    }

    return { currentUser };
  });
}

interface AdminRequestsData {
  currentUser: User;
}
