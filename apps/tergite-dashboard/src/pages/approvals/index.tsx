import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  allAdminProjectsQuery,
  currentUserQuery,
  myProjectsQuery,
  myRequestsQuery,
  refreshMyNotices,
  refreshMyProjectsQueries,
  refreshMyRequests,
} from "@/lib/api-client";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { useCallback, useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import {
  UserRole,
  type AppState,
  type User,
  type UserRequest,
} from "../../../types";
import { ApprovalsSidebar } from "./components/approvals-sidebar";
import { ApprovalsTable } from "./components/approvals-table";

export function Approvals() {
  const queryClient = useQueryClient();
  const { currentUser } = useLoaderData() as ApprovalsData;
  const { data: myProjects = [] } = useQuery(myProjectsQuery);
  // a superuser decides requests on projects they are not in, so sees them all
  const { data: adminProjects = [] } = useQuery(
    allAdminProjectsQuery({ currentUser }),
  );
  const projectList = useMemo(
    () => [...myProjects, ...adminProjects],
    [myProjects, adminProjects],
  );
  const { data: requests = [] } = useQuery(
    myRequestsQuery({ role: "approver", projectList }),
  );

  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedIdx = useMemo(() => {
    const selected = Object.entries(rowSelection).filter(
      ([_k, v]) => v === true,
    );
    return selected.length > 0 ? parseInt(selected[0][0]) : -1;
  }, [rowSelection]);

  const handleRowClick = useCallback(
    (row: Row<UserRequest>) => {
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection],
  );

  const handleReaction = useCallback(async () => {
    await refreshMyRequests(queryClient);
    await refreshMyNotices(queryClient);
    await refreshMyProjectsQueries(queryClient);
    setRowSelection({});
  }, [queryClient]);

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

      <ApprovalsSidebar
        request={requests[selectedIdx]}
        className="order-first xl:order-none col-span-1"
        onReaction={handleReaction}
      />
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<ApprovalsData> => {
    // no role gate: the API returns only what this user may act on, which is the
    // empty list for most people
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);
    const myProjects = await queryClient.ensureQueryData(myProjectsQuery);
    const adminProjects = currentUser.roles.includes(UserRole.ADMIN)
      ? await queryClient.ensureQueryData(allAdminProjectsQuery({ currentUser }))
      : [];
    await queryClient.ensureQueryData(
      myRequestsQuery({
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
