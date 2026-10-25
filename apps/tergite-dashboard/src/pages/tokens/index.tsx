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
  refreshMyTokensQueries,
} from "@/lib/api/tokens";
import { loadOrRedirectIfAuthErr } from "@/lib/loaders";
import { useAppStore } from "@/lib/app-state";
import {
  QueryClient,
  useQuery,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import {
  type AppToken,
  type ExtendedAppToken,
  type Project,
} from "types";
import { TokensTable } from "./components/tokens-table";
import { TokensSidebar } from "./components/tokens-sidebar";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { Progress } from "@/components/ui/progress";
import { findSelectedRow } from "@/components/ui/data-table/selection";

export function Tokens() {
  const queryClient = useQueryClient();
  const {
    currentProject,
    projects: defaultProjects,
    tokensQuery,
  } = useLoaderData() as TokensPageData;
  const [previousProject, setPreviousProject] = useState<Project>();
  const { data: projects = defaultProjects } = useQuery(myProjectsQuery);
  const { data: rawTokens, isPending } = useQuery(tokensQuery);
  const tokens = useMemo(
    () => rawTokens && addProjectNames(rawTokens, projects),
    [rawTokens, projects]
  );
  const projectName = useMemo(
    () => currentProject?.name ?? "all projects",
    [currentProject]
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedToken = findSelectedRow(tokens ?? [], rowSelection);

  const handleRowClick = useCallback(
    (row: Row<ExtendedAppToken>) => {
      if (!row.getIsSelected()) {
        row.toggleSelected();
        setRowSelection({ [row.id]: true });
      }
    },
    [setRowSelection]
  );

  const handleTokenDelete = useCallback(async () => {
    // before the refresh, or it would clear a row picked meanwhile
    setRowSelection({});
    await refreshMyTokensQueries(queryClient);
  }, [queryClient, setRowSelection]);

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
          {isPending && <Progress className="my-auto mx-auto" value={50} />}
          {!isPending && (
            <TokensTable
              data={tokens || []}
              onRowSelectionChange={setRowSelection}
              rowSelection={rowSelection}
              onRowClick={handleRowClick}
            />
          )}
        </CardContent>
      </Card>

      {tokens && (
        <TokensSidebar
          token={selectedToken}
          className="order-first xl:order-none col-span-1"
          onDelete={handleTokenDelete}
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    const { currentProjectId } = useAppStore.getState();
    // project object
    const cachedProjects: Project[] | undefined = queryClient.getQueryData(
      myProjectsQuery.queryKey
    );
    const projectList =
      cachedProjects ?? (await queryClient.fetchQuery(myProjectsQuery));

    const currentProject = projectList.filter(
      (v) => v.id === currentProjectId
    )[0];

    // tokens
    const tokensQuery = getMyTokensQuery({ project_id: currentProject?.id });

    return {
      currentProject,
      projects: projectList,
      tokensQuery,
    } as TokensPageData;
  });
}

interface TokensPageData {
  currentProject?: Project;
  projects: Project[];
  tokensQuery: UseQueryOptions<AppToken[]>;
}
