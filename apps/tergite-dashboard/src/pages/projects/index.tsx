import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { currentUserQuery } from "@/lib/api/auth";
import { getMyProjectsQpuTimeRequestsQuery, getMyRequestsQuery } from "@/lib/api/requests";
import { myProjectsQuery, refreshMyProjectsQueries } from "@/lib/api/projects";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  User,
  UserRequestStatus,
  type AppState,
  type Project,
} from "../../../types";
import { ProjectsTable } from "./components/project-table";
import { ProjectsSidebar } from "./components/projects-sidebar";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { Link, useLoaderData } from "react-router-dom";
import { RequestAccessDialog } from "./components/request-access-dialog";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function Projects() {
  const queryClient = useQueryClient();
  const { currentUser } = useLoaderData() as ProjectsPageData;
  const { data: projects = [] } = useQuery(myProjectsQuery);
  const { data: qpuTimeRequests = [] } = useQuery(
    getMyProjectsQpuTimeRequestsQuery({
      status: UserRequestStatus.PENDING,
      projects,
    })
  );
  const { data: pendingApprovals = [] } = useQuery(
    getMyRequestsQuery({ role: "approver", status: UserRequestStatus.PENDING }),
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedProject = findSelectedRow(projects ?? [], rowSelection);

  const handleRowClick = useCallback(
    (row: Row<Project>) => {
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection]
  );

  const handleProjectDelete = useCallback(async () => {
    // before the refresh, or it would clear a row picked meanwhile
    setRowSelection({});
    await refreshMyProjectsQueries(queryClient);
  }, [queryClient, setRowSelection]);

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card className="col-span-1 xl:pt-3 xl:col-span-3">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardDescription>Projects</CardDescription>
            <div className="flex items-center gap-2">
              {pendingApprovals.length > 0 && (
                <Link
                  to="/approvals"
                  data-cy-approvals-link
                  className="text-sm underline"
                >
                  {pendingApprovals.length} awaiting your approval
                </Link>
              )}
              <RequestAccessDialog />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ProjectsTable
            data={projects}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
            currentUser={currentUser}
            qpuTimeRequests={qpuTimeRequests}
          />
        </CardContent>
      </Card>

      <ProjectsSidebar
        project={selectedProject}
        className="order-first xl:order-none col-span-1"
        onDelete={handleProjectDelete}
        canDelete={
          selectedProject?.admin_id === currentUser.id &&
          // the API refuses the owner deleting their own, superusers aside
          !selectedProject?.is_personal
        }
      />
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<ProjectsPageData> => {
    const cachedCurrentUser = queryClient.getQueryData(
      currentUserQuery.queryKey
    );
    const currentUser =
      cachedCurrentUser ?? (await queryClient.fetchQuery(currentUserQuery));
    return { currentUser };
  });
}

interface ProjectsPageData {
  currentUser: User;
}
