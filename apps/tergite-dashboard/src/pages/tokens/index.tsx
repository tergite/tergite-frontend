import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  myProjectsQuery,
  myTokensQuery,
  refreshMyTokensQueries,
} from "@/lib/api-client";
import { loadOrRedirectIfAuthErr } from "@/lib/utils";
import {
  QueryClient,
  useQuery,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { type AppState, type ExtendedAppToken, type Project } from "types";
import { TokensTable } from "./components/tokens-table";
import { TokensSidebar } from "./components/tokens-sidebar";
import { Row, RowSelectionState } from "@tanstack/react-table";
import { Progress } from "@/components/ui/progress";

export function Tokens() {
  const queryClient = useQueryClient();
  const { currentProject, tokensQuery } = useLoaderData() as TokensPageData;
  const [previousProject, setPreviousProject] = useState<Project>();
  const { data: tokens, isPending } = useQuery(tokensQuery);
  const projectName = useMemo(
    () => currentProject?.name ?? "all projects",
    [currentProject]
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedTokenIdx = useMemo(() => {
    const selectedEntries = Object.entries(rowSelection).filter(
      ([_k, v]) => v === true
    );
    if (selectedEntries.length > 0) {
      return parseInt(selectedEntries[0][0]);
    }
    return -1;
  }, [rowSelection]);

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
    await refreshMyTokensQueries(queryClient);
    // clear selected rows
    setRowSelection({});
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
          token={tokens[selectedTokenIdx]}
          className="order-first xl:order-none col-span-1"
          onDelete={handleTokenDelete}
        />
      )}
    </main>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function loader(appState: AppState, queryClient: QueryClient) {
  return loadOrRedirectIfAuthErr(async () => {
    // project object
    const cachedProjects: Project[] | undefined = queryClient.getQueryData(
      myProjectsQuery.queryKey
    );
    const projectList =
      cachedProjects ?? (await queryClient.fetchQuery(myProjectsQuery));

    const currentProject = projectList.filter(
      (v) => v.ext_id === appState.currentProjectExtId
    )[0];

    // tokens
    const tokensQuery = myTokensQuery({
      project_ext_id: currentProject?.ext_id,
      projectList,
    });

    return {
      currentProject,
      tokensQuery,
    } as TokensPageData;
  });
}

interface TokensPageData {
  currentProject?: Project;
  tokensQuery: UseQueryOptions<ExtendedAppToken[]>;
}
