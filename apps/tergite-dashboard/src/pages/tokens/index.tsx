import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { myProjectsQuery } from "@/lib/api/projects";
import {
  addProjectNames,
  getMyTokensQuery,
} from "@/lib/api/tokens";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { useAppStore } from "@/lib/app-state";
import {
  QueryClient,
  useQuery,
} from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import {
  type AppToken,
  type ExtendedAppToken,
  type Project,
} from "types";
import { TokensTable } from "./components/tokens-table";
import { TokenSummary } from "./components/tokens-sidebar";
import { SidebarPlaceholder } from "@/components/ui/sidebar-placeholder";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function Tokens() {
  const {
    currentProject,
    projects: defaultProjects,
    tokens: defaultTokens,
  } = useLoaderData() as TokensPageData;
  const [previousProject, setPreviousProject] = useState<Project>();
  const { data: projects = defaultProjects } = useQuery(myProjectsQuery);
  const { data: rawTokens = defaultTokens } = useQuery(
    getMyTokensQuery({ project_id: currentProject?.id })
  );
  const tokens = useMemo(
    () => addProjectNames(rawTokens, projects),
    [rawTokens, projects]
  );
  const projectName = useMemo(
    () => currentProject?.name ?? "all projects",
    [currentProject]
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedToken = findSelectedRow(tokens, rowSelection);

  const handleRowClick = useCallback(
    (row: Row<ExtendedAppToken>) => {
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection]
  );

  const handleTokenDelete = useCallback(() => {
    setRowSelection({});
  }, [setRowSelection]);

  useEffect(() => {
    // track the changes in current project and reset the current token when projects change
    if (previousProject?.id != currentProject?.id) {
      setPreviousProject(currentProject);

      // clear selection
      setRowSelection({});
    }
  }, [currentProject, previousProject, setPreviousProject, setRowSelection]);

  return (
    <main className="grid flex-1 items-start gap-4 grid-cols-1 p-4 sm:px-6 sm:py-0 xl:grid-cols-4">
      <Card className="col-span-1 xl:pt-3 xl:col-span-3">
        <CardHeader>
          <CardDescription>API tokens for {projectName}</CardDescription>
        </CardHeader>
        <CardContent>
          <TokensTable
            data={tokens}
            onRowSelectionChange={setRowSelection}
            rowSelection={rowSelection}
            onRowClick={handleRowClick}
          />
        </CardContent>
      </Card>

      {selectedToken ? (
        <TokenSummary
          token={selectedToken}
          className="order-first xl:order-none col-span-1"
          onDelete={handleTokenDelete}
        />
      ) : (
        <SidebarPlaceholder
          mainTitle="Token title"
          contentTitle="Token details"
          contentDetail="Click any row to show details here"
          className="order-first xl:order-none col-span-1"
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async (): Promise<TokensPageData> => {
    const { currentProjectId } = useAppStore.getState();
    const projects = await queryClient.ensureQueryData(myProjectsQuery);
    const currentProject = projects.find((v) => v.id === currentProjectId);
    const tokens = await queryClient.ensureQueryData(
      getMyTokensQuery({ project_id: currentProject?.id })
    );
    return { currentProject, projects, tokens };
  });
}

interface TokensPageData {
  currentProject?: Project;
  projects: Project[];
  tokens: AppToken[];
}
