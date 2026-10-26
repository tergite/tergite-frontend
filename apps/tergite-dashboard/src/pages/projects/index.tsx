import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { currentUserQuery } from "@/lib/api/auth";
import {
  getMyProjectsQpuTimeRequestsQuery,
  getMyRequestsQuery,
} from "@/lib/api/requests";
import { myProjectsQuery } from "@/lib/api/projects";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { QueryClient, useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { User, Project } from "@/lib/api/types";
import { ProjectsTable } from "./components/project-table";
import { ProjectSummary } from "./components/projects-sidebar";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { Link, useLoaderData } from "react-router-dom";
import { RequestAccessDialog } from "./components/request-access-dialog";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function Projects() {
  const { currentUser } = useLoaderData() as ProjectsPageData;
  const { data: projects = [] } = useQuery(myProjectsQuery);
  const { data: qpuTimeRequests = [] } = useQuery(
    getMyProjectsQpuTimeRequestsQuery({
      status: "pending",
      projects,
    })
  );
  const { data: pendingApprovals = [] } = useQuery(
    getMyRequestsQuery({ role: "approver", status: "pending" }),
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

  const handleProjectDelete = useCallback(() => {
    setRowSelection({});
  }, [setRowSelection]);

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

      {selectedProject ? (
        <ProjectSummary
          project={selectedProject}
          className="order-first xl:order-none col-span-1"
          onDelete={handleProjectDelete}
          isDeletable={
            selectedProject.admin_id === currentUser.id &&
            // the API refuses the owner deleting their own, superusers aside
            !selectedProject.is_personal
          }
        />
      ) : (
        <SidebarPlaceholder
          mainTitle="Project title"
          contentTitle="Project details"
          contentDetail="Click any row to show details here"
          className="order-first xl:order-none col-span-1"
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<ProjectsPageData> => {
    const currentUser = await queryClient.ensureQueryData(currentUserQuery);
    return { currentUser };
  });
}

interface ProjectsPageData {
  currentUser: User;
}
