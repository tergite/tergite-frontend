import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { getAllAdminProjectsQuery, myProjectsQuery } from "@/lib/api/projects";
import { currentUserQuery } from "@/lib/api/auth";
import { getMyRequestsQuery } from "@/lib/api/requests";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { type User, type UserRequest } from "@/lib/api/types";
import { ApprovalSummary } from "./components/approvals-sidebar";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";
import { ApprovalsTable } from "./components/approvals-table";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function Approvals() {
  const { currentUser } = useLoaderData() as ApprovalsData;
  const { data: myProjects = [] } = useQuery(myProjectsQuery);
  // a superuser decides requests on projects they are not in, so sees them all
  const { data: adminProjects = [] } = useQuery(
    getAllAdminProjectsQuery({ currentUser }),
  );
  const projectList = useMemo(
    () => [...myProjects, ...adminProjects],
    [myProjects, adminProjects],
  );
  const { data: requests = [] } = useQuery(
    getMyRequestsQuery({ role: "approver", projectList }),
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
    [setRowSelection],
  );

  const handleReaction = useCallback(() => {
    setRowSelection({});
  }, []);

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card className="col-span-1 xl:col-span-3">
        <CardHeader>
          <CardDescription>Requests awaiting your approval</CardDescription>
        </CardHeader>
        <CardContent>
          <ApprovalsTable
            data={requests}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      {selectedRequest ? (
        <ApprovalSummary
          request={selectedRequest}
          className="order-first xl:order-none col-span-1"
          onReaction={handleReaction}
        />
      ) : (
        <SidebarPlaceholder
          mainTitle="Request"
          contentTitle="Request details"
          contentDetail="Click any row to show details here"
          className="order-first xl:order-none col-span-1"
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<ApprovalsData> => {
    // no role gate: the API returns only what this user may act on, which is the
    // empty list for most people
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);
    const myProjects = await queryClient.ensureQueryData(myProjectsQuery);
    const adminProjects = currentUser.roles.includes("admin")
      ? await queryClient.ensureQueryData(getAllAdminProjectsQuery({ currentUser }))
      : [];
    await queryClient.ensureQueryData(
      getMyRequestsQuery({
        role: "approver",
        projectList: [...myProjects, ...adminProjects],
      }),
    );
    return { currentUser };
  });
}

interface ApprovalsData {
  currentUser: User;
}
