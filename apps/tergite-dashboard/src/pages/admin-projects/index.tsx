import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  allAdminProjectsQuery,
  currentUserQuery,
  refreshAllAdminQueries,
  refreshMyProjectsQueries,
} from "@/lib/api-client";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
  ErrorInfo,
  User,
  UserRole,
  type AppState,
  type AdminProject,
} from "../../../types";
import { AdminProjectsTable } from "./components/projects-table";
import { AdminProjectsSidebar } from "./components/projects-sidebar";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { useLoaderData } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { CreateProjectForm } from "./components/create-project-form";

export function AdminProjects() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<OperationMode>(OperationMode.EDIT);
  // const [isCreating, setIsCreating] = useState(false);
  // const [isEditing, setIsEditing] = useState(false);
  const { currentUser } = useLoaderData() as AdminProjectsData;
  const { data: projects = [] } = useQuery(
    allAdminProjectsQuery({
      currentUser,
    })
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedProjectIdx = useMemo(() => {
    const selectedEntries = Object.entries(rowSelection).filter(
      ([_k, v]) => v === true
    );
    if (selectedEntries.length > 0) {
      return parseInt(selectedEntries[0][0]);
    }
    return -1;
  }, [rowSelection]);

  const handleRowClick = useCallback(
    (row: Row<AdminProject>) => {
      setMode(OperationMode.EDIT);
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection, setMode]
  );

  const handleProjectDelete = useCallback(async () => {
    await refreshMyProjectsQueries(queryClient);
    await refreshAllAdminQueries(queryClient);
    // clear selected rows
    setRowSelection({});
  }, [queryClient, setRowSelection]);

  const handleProjectEdit = useCallback(async () => {
    setMode(OperationMode.EDIT);
    await refreshMyProjectsQueries(queryClient);
    await refreshAllAdminQueries(queryClient);
  }, [queryClient, setMode]);

  const handleProjectCreate = useCallback(async () => {
    setMode(OperationMode.EDIT);
    await refreshMyProjectsQueries(queryClient);
    await refreshAllAdminQueries(queryClient);
    setRowSelection({});
  }, [queryClient, setMode, setRowSelection]);

  const handleSidebarClose = useCallback(async () => {
    setMode(OperationMode.EDIT);
    setRowSelection({});
  }, [setMode, setRowSelection]);

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card id="projects-table" className="col-span-1 xl:pt-3 xl:col-span-3">
        <CardHeader>
          <div className="flex justify-between">
            <CardDescription>Projects</CardDescription>
            <div className="flex gap-2">
              <Button
                variant="default"
                onClick={() => {
                  setMode(OperationMode.CREATE);
                }}
              >
                New
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <AdminProjectsTable
            data={projects}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      {mode === OperationMode.EDIT && (
        <AdminProjectsSidebar
          project={projects[selectedProjectIdx]}
          className="order-first xl:order-none col-span-1"
          onDelete={handleProjectDelete}
          onEdit={handleProjectEdit}
          onClose={handleSidebarClose}
        />
      )}

      {mode === OperationMode.CREATE && (
        <CreateProjectForm
          className="order-first xl:order-none col-span-1"
          onCreate={handleProjectCreate}
          onCancel={handleSidebarClose}
          onClose={handleSidebarClose}
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(_appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<AdminProjectsData> => {
    const cachedCurrentUser = queryClient.getQueryData(
      currentUserQuery.queryKey
    );
    const currentUser =
      cachedCurrentUser ?? (await queryClient.fetchQuery(currentUserQuery));

    if (!currentUser.roles.includes(UserRole.ADMIN)) {
      const error = new Error("user should be an admin") as ErrorInfo;
      error.status = 403;
      throw error;
    }

    return { currentUser };
  });
}

interface AdminProjectsData {
  currentUser: User;
}

enum OperationMode {
  EDIT = "edit",
  CREATE = "create",
}
